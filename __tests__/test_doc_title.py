import src.edgar_cli as cli


def test_process_quarter_uses_form(monkeypatch, tmp_path):
    html_path = tmp_path / "dummy.html"
    html_path.write_text("<html></html>")

    def fake_fetch_html_asset(ticker, year, quarter):
        return {"kind": "ixbrl", "path": html_path, "form": "10-Q"}

    captured = []

    def fake_process_html(html, title, folder_id):
        captured.append(title)
        return [], "https://doc"

    monkeypatch.setattr(cli, "fetch_html_asset", fake_fetch_html_asset)
    monkeypatch.setattr(cli, "process_html", fake_process_html)

    url = cli.process_quarter(
        "TEST",
        2024,
        1,
        drive_service=None,
        quarter_folder_id="id",
    )
    assert url == "https://doc"

    assert captured == ["TEST 2024 Q1 - 10Q"]
