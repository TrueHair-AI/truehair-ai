// Per-user encrypted gallery: AES-GCM blobs in IndexedDB.
//
// Design constraints (issue #106):
// - Server never stores generated images (IRB-era rule preserved as product
//   policy). Only the client holds the WebP bytes.
// - Encryption key is derived from `${user_id}:${storage_salt}` via PBKDF2 +
//   AES-GCM, so a different account on the same browser cannot decrypt the
//   previous user's blobs.
// - Records are keyed by `[user_id, generated_image_id]` and indexed by
//   `user_id`, so loadAllForCurrentUser() never even surfaces another user's
//   ciphertext (the encryption layer is the second line of defense).
//
// Public surface:
//   - persistGeneratedImage(blob, { id, hairstyle_name, created_at? })
//   - loadAllForCurrentUser() -> [{ id, hairstyle_name, created_at, blob }]

const DB_NAME = "truehair_gallery";
const DB_VERSION = 1;
const STORE = "visualizations";
const PBKDF2_ITERATIONS = 100_000;

let cachedKey = null;

async function getKey() {
    if (cachedKey) return cachedKey;
    const res = await fetch("/api/me/storage-key", { credentials: "same-origin" });
    if (!res.ok) {
        throw new Error(`storage-key fetch failed: ${res.status}`);
    }
    const { user_id, salt } = await res.json();
    const enc = new TextEncoder();
    const seed = enc.encode(`${user_id}:${salt}`);
    const baseKey = await crypto.subtle.importKey(
        "raw",
        seed,
        "PBKDF2",
        false,
        ["deriveKey"],
    );
    const key = await crypto.subtle.deriveKey(
        {
            name: "PBKDF2",
            salt: enc.encode(salt),
            iterations: PBKDF2_ITERATIONS,
            hash: "SHA-256",
        },
        baseKey,
        { name: "AES-GCM", length: 256 },
        false,
        ["encrypt", "decrypt"],
    );
    cachedKey = { key, user_id };
    return cachedKey;
}

function openDB() {
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORE)) {
                const store = db.createObjectStore(STORE, {
                    keyPath: ["user_id", "id"],
                });
                store.createIndex("by_user", "user_id");
            }
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function encryptBlob(key, blob) {
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const buf = await blob.arrayBuffer();
    const ciphertext = await crypto.subtle.encrypt(
        { name: "AES-GCM", iv },
        key,
        buf,
    );
    return { iv, ciphertext };
}

async function decryptBlob(key, { iv, ciphertext }) {
    const buf = await crypto.subtle.decrypt(
        { name: "AES-GCM", iv },
        key,
        ciphertext,
    );
    return new Blob([buf], { type: "image/webp" });
}

export async function persistGeneratedImage(blob, metadata) {
    if (!blob) throw new Error("persistGeneratedImage: missing blob");
    if (metadata == null || metadata.id == null) {
        throw new Error("persistGeneratedImage: missing metadata.id");
    }

    const { key, user_id } = await getKey();
    const { iv, ciphertext } = await encryptBlob(key, blob);
    const db = await openDB();

    return new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readwrite");
        tx.objectStore(STORE).put({
            id: metadata.id,
            user_id,
            hairstyle_name: metadata.hairstyle_name || "",
            created_at: metadata.created_at || new Date().toISOString(),
            iv,
            ciphertext,
        });
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
        tx.onabort = () => reject(tx.error);
    });
}

export async function loadAllForCurrentUser() {
    const { key, user_id } = await getKey();
    const db = await openDB();

    const records = await new Promise((resolve, reject) => {
        const tx = db.transaction(STORE, "readonly");
        const req = tx.objectStore(STORE).index("by_user").getAll(user_id);
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
    });

    const decrypted = [];
    for (const rec of records) {
        try {
            const blob = await decryptBlob(key, {
                iv: rec.iv,
                ciphertext: rec.ciphertext,
            });
            decrypted.push({
                id: rec.id,
                hairstyle_name: rec.hairstyle_name,
                created_at: rec.created_at,
                blob,
            });
        } catch (e) {
            // Almost always means a different user's record (key mismatch). The
            // user_id index above already filters those out, so this branch is
            // a true integrity failure — record id but not the bytes.
            console.warn(`gallery: failed to decrypt record id=${rec.id}`, e);
        }
    }

    decrypted.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return decrypted;
}
