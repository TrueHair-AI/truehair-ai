def test_index(client):
    """Test the index page."""
    response = client.get("/")
    assert response.status_code == 200


def test_dashboard_redirect_unauthenticated(client):
    """Test that unauthorized users are redirected from the dashboard."""
    response = client.get("/dashboard")
    assert response.status_code == 302


def test_stylists_page(client):
    """Test the stylists directory page."""
    response = client.get("/stylists")
    assert response.status_code in [200, 302]
