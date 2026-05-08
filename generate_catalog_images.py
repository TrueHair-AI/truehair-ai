"""
Generate catalog preview images via Vertex AI (gemini-2.5-flash-image).

One-off tooling. Run from project root:

    uv run python generate_catalog_images.py            # generate any missing images
    uv run python generate_catalog_images.py --force    # regenerate all
    uv run python generate_catalog_images.py lob curly_bob  # only specific slugs

Auth: relies on Application Default Credentials (gcloud auth application-default
login) and GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION from the .env file
(loaded via python-dotenv). Output: app/static/images/<slug>_preview.png.
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image

load_dotenv()

OUTPUT_DIR = Path("app/static/images")
MODEL = "gemini-2.5-flash-image"

# Prompts intentionally vary subject demographics (age, gender, ethnicity, hair
# texture) so the catalog as a whole reflects the diversity goal in issue #65.
# Each prompt asks for a clean, editorial portrait suitable for a square card.
BASE_STYLE = (
    "Photorealistic editorial portrait, head-and-shoulders, soft studio "
    "lighting, plain neutral light-gray background, sharp focus on hair, "
    "natural skin tone, friendly relaxed expression, looking toward the "
    "camera. Square 1:1 framing. No text, watermarks, or logos."
)

PROMPTS: dict[str, str] = {
    "lob": (
        "A woman in her mid-30s of East Asian descent with a sleek shoulder-"
        "length 'lob' (long bob). Hair is straight to slightly wavy (type 1B-"
        "2A), one-length with a subtle inward curve at the ends, glossy and "
        "healthy-looking. " + BASE_STYLE
    ),
    "layered_cut_bangs": (
        "A woman in her early 50s with natural silver-gray hair, fair skin, "
        "wearing a medium-length layered cut with soft, face-framing curtain "
        "bangs. Hair is straight to gently wavy (type 1A-2A), layers visibly "
        "adding movement around the jawline. " + BASE_STYLE
    ),
    "sleek_high_ponytail": (
        "A young Latina woman in her 20s with rich dark-brown hair pulled "
        "tightly into a sleek, high ponytail that sits at the crown. The "
        "base is smooth and polished with no flyaways; the ponytail itself "
        "is long and slightly wavy (type 2B-2C). " + BASE_STYLE
    ),
    "top_knot_bun": (
        "An androgynous person in their late 20s of mixed heritage, with "
        "long curly hair (type 3A-3B) gathered high on the crown into a "
        "loose, lived-in top-knot bun. A few soft tendrils frame the face. "
        + BASE_STYLE
    ),
    "bantu_knots": (
        "A Black woman in her 30s with dark skin and a full head of neatly "
        "sectioned Bantu knots — small, sculpted knots arranged in clean "
        "geometric rows across the scalp. Hair is type 4B-4C. The style "
        "looks freshly installed and well-defined. " + BASE_STYLE
    ),
    "senegalese_twists": (
        "A Black woman in her 40s with medium-brown skin wearing long "
        "Senegalese twists in a natural dark-brown color — smooth, rope-"
        "like two-strand twists falling past the shoulders. Hair is type 4A-"
        "4B underneath. The twists are uniform and freshly installed. " + BASE_STYLE
    ),
    "goddess_braids": (
        "A young Black woman in her 20s with deep-brown skin wearing thick "
        "goddess braids — large cornrow-style braids laid flat against the "
        "scalp in a striking front-to-back pattern, with the braided lengths "
        "trailing past the shoulders. Hair type 4A-4C. " + BASE_STYLE
    ),
    "curly_bob": (
        "A young woman in her mid-20s of mixed Latina heritage with a chin-"
        "length curly bob. Hair is springy and well-defined (type 3B), "
        "shaped to frame the jawline with bouncy volume. Natural dark-brown "
        "color. " + BASE_STYLE
    ),
    "mohawk": (
        "A man in his early 30s of Middle Eastern descent wearing a "
        "dramatic, traditional mohawk: the entire sides of the head are "
        "shaved completely down to bare skin, leaving only a narrow strip "
        "of dark hair (about 5 cm wide) running from the forehead to the "
        "back of the head. The center strip is long and styled straight "
        "upward into a tall, peaked fin. Hair type 2A-2B. " + BASE_STYLE
    ),
    "faux_hawk": (
        "A Black woman in her late 20s wearing a soft faux hawk — sides "
        "kept short (not shaved) with the curls in the center swept upward "
        "into a defined peak. Hair is natural type 3C-4A, dark brown. " + BASE_STYLE
    ),
}


def get_client() -> genai.Client:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    if not project:
        sys.exit("GOOGLE_CLOUD_PROJECT not set — check .env or export it")
    return genai.Client(vertexai=True, project=project, location=location)


def generate_one(client: genai.Client, slug: str, prompt: str, force: bool) -> Path:
    out_path = OUTPUT_DIR / f"{slug}_preview.png"
    if out_path.exists() and not force:
        print(f"  [skip] {out_path} already exists (use --force to regenerate)")
        return out_path

    print(f"  [generate] {slug} -> {out_path}")
    response = client.models.generate_content(
        model=MODEL,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            http_options=types.HttpOptions(timeout=120000),
        ),
    )

    image_part = next((p for p in response.parts if p.inline_data), None)
    if not image_part:
        raise RuntimeError(f"No image returned for slug={slug}")

    img = Image.open(io.BytesIO(image_part.inline_data.data))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    print(f"    saved {img.size[0]}x{img.size[1]} -> {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "slugs",
        nargs="*",
        help="Optional list of slugs to generate. Default: all known slugs.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if the output file already exists.",
    )
    args = parser.parse_args()

    targets = args.slugs or list(PROMPTS.keys())
    unknown = [s for s in targets if s not in PROMPTS]
    if unknown:
        sys.exit(f"Unknown slugs: {unknown}. Known: {sorted(PROMPTS)}")

    client = get_client()
    print(f"Generating {len(targets)} image(s) into {OUTPUT_DIR}/ ...")
    for slug in targets:
        try:
            generate_one(client, slug, PROMPTS[slug], args.force)
        except Exception as exc:
            print(f"  [error] {slug}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    main()
