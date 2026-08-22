"""Offline venue starters remain local, complete, and structurally compilable."""

from researchos.documents.latex_parse import parse_document
from researchos.documents.schemas import CreateLatexProjectRequest
from researchos.documents.venue_templates import VENUE_TEMPLATES


def test_venue_template_catalog_is_complete_and_parseable() -> None:
    assert set(VENUE_TEMPLATES) == {"neurips", "icml", "iclr", "cvpr", "acl", "aaai"}
    for template_id, template in VENUE_TEMPLATES.items():
        payload = CreateLatexProjectRequest(name=template.venue, template_id=template_id)
        assert payload.template_id == template_id
        assert template.official_url.startswith("https://")
        assert "\\begin{document}" in template.main_tex
        assert "\\bibliography{references}" in template.main_tex
        preview, diagnostics = parse_document({"main.tex": template.main_tex}, "main.tex")
        assert preview["sections"]
        assert not [item for item in diagnostics if item.get("severity") == "error"]
