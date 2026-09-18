import json, sys, yaml
from pathlib import Path
sys.path.insert(0, str(Path("src").resolve()))
from deltafuse.core.frontmatter import parse_frontmatter, replace_frontmatter
from deltafuse.core.schemas import SchemaRegistry
from deltafuse.core.scaffold import _change_yaml
r = SchemaRegistry(Path("process/schemas"))
source = "---\nid: TASK-001\nid: TASK-002\n---\n\n# Body\n\n"
meta, body = parse_frontmatter(source)
decision = {"id":"DEC-0001","title":"Example","kind":"product","status":"proposed","owner":"human","affects":{"capabilities":[],"spec_refs":[]},"date":"not-a-date"}
result = {"probe_kind":"read-only in-memory characterization","python":sys.version.split()[0],"yaml":yaml.__version__,"duplicate_frontmatter_id":meta["id"],"original_body_suffix":repr(source.split("---",2)[2]),"parsed_body":repr(body),"updated_body_suffix":repr(replace_frontmatter(source,{"id":"TASK-003"}).split("---",2)[2]),"scaffold_schema_errors":r.validate("change",_change_yaml("CHG-001","code","2026-09-18T00:00:00Z")),"invalid_date_schema_errors":r.validate("decision",decision)}
print(json.dumps(result, ensure_ascii=False,indent=2))
