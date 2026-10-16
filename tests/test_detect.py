import pytest

from environment_detector.detect import analyze


def names(result, category):
    return [item["name"] for item in result["technologies"][category]]


@pytest.mark.parametrize("html,category,name,confidence", [
    ('<meta name="generator" content="WordPress 6.8.1">', "cms", "WordPress", .95),
    ('<script src="/wp-content/plugins/shop/main.js"></script>', "cms", "WordPress", .65),
    ('<img src="https://cdn.imweb.me/upload/image.png">', "cms", "Imweb", .55),
    ('<img src="//img.echosting.cafe24.com/skin/base/a.gif">', "cms", "Cafe24", .55),
    ('<script src="/_next/static/chunks/app.js"></script>', "frontend", "Next.js", .8),
])
def test_html_rules(html, category, name, confidence):
    result = analyze({}, html, "https://example.com/")
    item = result["technologies"][category][0]
    assert item["name"] == name
    assert item["confidence"] == confidence
    assert item["evidence"][0]["reference"].startswith("https://")
    assert item["evidence"][0]["value"]
    assert result["development_model"]["name"] == "UNKNOWN"
    assert names(result, "backend") == ["UNKNOWN"]


@pytest.mark.parametrize("headers,category,name", [
    ({"X-Powered-By": "Next.js"}, "frontend", "Next.js"),
    ({"x-powered-by": "Express"}, "backend", "Express"),
    ({"x-powered-by": "PHP/8.4.1"}, "backend", "PHP"),
    ({"Server": "nginx/1.28.0"}, "server", "nginx/1.28.0"),
    ({"cf-ray": "0123456789abcdef-ICN"}, "cdn", "Cloudflare"),
])
def test_headers(headers, category, name):
    assert names(analyze(headers, "", "https://example.com"), category) == [name]


@pytest.mark.parametrize("html", [
    "<p>WordPress Imweb Cafe24 React Django nginx</p>",
    '<!-- <meta name="generator" content="WordPress"> -->',
    '<a href="https://cdn.imweb.me/upload/a.png">link</a>',
    '<img src="https://cdn.imweb.me.attacker.com/a.png">',
    '<img src="https://cdn.imweb.me@attacker.com/a.png">',
    '<script src="https://example.com/app.js?path=/wp-content/themes/a/"></script>',
    '<script>const demo = "<meta name=generator content=WordPress>"</script>',
    '<meta name="generator" content="WordPress-ish">',
    '<div id="root"></div><script src="/custom-app.js"></script>',
    '<img src="https://[broken">',
])
def test_no_guesses_from_text_comments_generic_assets_or_spoofed_host(html):
    result = analyze({}, html, "https://example.com")
    assert all(names(result, category) == ["UNKNOWN"] for category in result["technologies"])


def test_multiple_signals_and_platform_candidates_are_preserved():
    html = '<meta name="GENERATOR" content="WordPress"><script src="/wp-content/themes/a/main.js"></script><img src="https://cdn.imweb.me/a.png">'
    result = analyze({"server": "cloudflare", "cf-ray": "0123456789abcdef-ICN"}, html, "https://example.com")
    assert names(result, "cms") == ["WordPress", "Imweb"]
    assert len(result["technologies"]["cms"][0]["evidence"]) == 2
    assert result["technologies"]["cms"][0]["confidence"] == .95
    assert names(result, "backend") == ["UNKNOWN"]


def test_evidence_count_and_length_are_bounded():
    html = "".join(f'<script src="/wp-content/themes/a/{i}{"x" * 500}.js"></script>' for i in range(30))
    evidence = analyze({}, html, "https://example.com")["technologies"]["cms"][0]["evidence"]
    assert len(evidence) == 10
    assert all(len(item["value"]) <= 300 for item in evidence)
