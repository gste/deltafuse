import pytest
from deltafuse.core.frontmatter import parse_frontmatter, FrontmatterParseError

def test_parse_valid_frontmatter():
    text = """---
id: TASK-001
status: ready
---
# Body content
Here is some description.
"""
    meta, body = parse_frontmatter(text)
    assert meta == {"id": "TASK-001", "status": "ready"}
    assert body.strip() == "# Body content\nHere is some description."

def test_parse_missing_delimiters():
    text = "# Just markdown without frontmatter"
    with pytest.raises(FrontmatterParseError, match="File does not contain valid YAML frontmatter"):
        parse_frontmatter(text)

def test_parse_invalid_yaml_frontmatter():
    text = """---
id: [unclosed list
---
Body
"""
    with pytest.raises(FrontmatterParseError, match="YAML parsing error"):
        parse_frontmatter(text)

def test_parse_non_dict_frontmatter():
    text = """---
- just
- a
- list
---
Body
"""
    with pytest.raises(FrontmatterParseError, match="Frontmatter YAML must be a mapping/dict"):
        parse_frontmatter(text)
