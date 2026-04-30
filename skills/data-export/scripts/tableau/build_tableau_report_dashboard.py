#!/usr/bin/env python3
from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

def _find_workspace_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / "runtime").is_dir() and (candidate / "skills").is_dir():
            return candidate
    raise RuntimeError(f"Unable to locate workspace root from {start}")


WORKSPACE = _find_workspace_root(Path(__file__).resolve())
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from runtime.paths import runtime_db_path  # noqa: E402

RUNTIME_TABLEAU_DIR = WORKSPACE / "runtime" / "tableau"
MAINT_DIR = WORKSPACE / "jobs" / "_maintenance"

DB_BEFORE_SYNC = MAINT_DIR / "registry_before_20260320_1121.db"
DB_BEFORE_ENRICH = MAINT_DIR / "registry_before_enrich_20260320_1334.db"
DB_CURRENT = runtime_db_path()
OUT_HTML = RUNTIME_TABLEAU_DIR / "配置变更汇报看板.html"

MISSING = object()


def load_db(path: Path) -> dict[str, dict[str, Any]]:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    entries = {
        str(r["entry_key"]): json.loads(r["payload_json"])
        for r in cur.execute("SELECT entry_key, payload_json FROM entries")
    }
    specs = {
        str(r["entry_key"]): json.loads(r["spec_json"])
        for r in cur.execute("SELECT entry_key, spec_json FROM specs")
    }
    conn.close()
    return {
        key: {"entry": entries.get(key) or {}, "spec": specs.get(key) or {}}
        for key in sorted(set(entries) | set(specs))
    }


def list_names(items: list[Any], field: str = "name") -> list[str]:
    out: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            v = item.get(field)
            if isinstance(v, str) and v:
                out.append(v)
        elif isinstance(item, str) and item:
            out.append(item)
    return out


def match_item(items: list[Any], current: dict[str, Any]) -> dict[str, Any] | None:
    current_name = current.get("tableau_field") or current.get("key") or current.get("display_name")
    for item in items or []:
        if not isinstance(item, dict):
            continue
        name = item.get("tableau_field") or item.get("key") or item.get("display_name")
        if name == current_name:
            return item
    return None


def comment(prev: Any) -> str:
    if prev is MISSING:
        return " # 修改前：无"
    return f" # 修改前：{json.dumps(prev, ensure_ascii=False)}"


def annotated_json_lines(current: Any, previous: Any = MISSING, indent: int = 0) -> list[str]:
    space = "  " * indent
    if isinstance(current, dict):
        keys = list(current.keys())
        lines = [space + "{"]
        for idx, key in enumerate(keys):
            value = current[key]
            prev_value = previous.get(key, MISSING) if isinstance(previous, dict) else MISSING
            suffix = "," if idx < len(keys) - 1 else ""
            key_prefix = f'{space}  {json.dumps(key, ensure_ascii=False)}: '
            if isinstance(value, dict):
                open_line = key_prefix + "{"
                if prev_value is MISSING:
                    open_line += " # 修改前：无"
                lines.append(open_line)
                inner_keys = list(value.keys())
                for inner_idx, inner_key in enumerate(inner_keys):
                    inner_val = value[inner_key]
                    inner_prev = prev_value.get(inner_key, MISSING) if isinstance(prev_value, dict) else MISSING
                    inner_suffix = "," if inner_idx < len(inner_keys) - 1 else ""
                    line = f'{space}    {json.dumps(inner_key, ensure_ascii=False)}: {json.dumps(inner_val, ensure_ascii=False)}{inner_suffix}'
                    if inner_prev is MISSING or inner_prev != inner_val:
                        line += comment(inner_prev)
                    lines.append(line)
                lines.append(space + "  }" + suffix)
            else:
                line = key_prefix + f'{json.dumps(value, ensure_ascii=False)}{suffix}'
                if prev_value is MISSING or prev_value != value:
                    line += comment(prev_value)
                lines.append(line)
        lines.append(space + "}")
        return lines
    return [space + json.dumps(current, ensure_ascii=False)]


def annotated_json(current: dict[str, Any], previous: dict[str, Any] | None) -> str:
    return "\n".join(annotated_json_lines(current, previous if previous is not None else MISSING))


def item_status(current: dict[str, Any]) -> str:
    missing = []
    for key in ["key", "display_name", "kind", "apply_via"]:
        if key in current and not current.get(key):
            missing.append(key)
    if missing:
        return "部分完成"
    if current.get("validation"):
        return "已补规则"
    return "已补结构"


def human_sync_summary(before_sync_payload: dict[str, Any], before_enrich_payload: dict[str, Any]) -> list[str]:
    old_entry = before_sync_payload.get("entry") or {}
    new_entry = before_enrich_payload.get("entry") or {}
    old_spec = before_sync_payload.get("spec") or {}
    new_spec = before_enrich_payload.get("spec") or {}
    bullets: list[str] = []

    old_dims = set(list_names(old_spec.get("dimensions") or []))
    new_dims = set(list_names(new_spec.get("dimensions") or []))
    old_measures = set(list_names(old_spec.get("measures") or []))
    new_measures = set(list_names(new_spec.get("measures") or []))
    old_filters = {x.get("tableau_field") or x.get("key") for x in old_spec.get("filters", []) if isinstance(x, dict)}
    new_filters = {x.get("tableau_field") or x.get("key") for x in new_spec.get("filters", []) if isinstance(x, dict)}
    old_params = {x.get("tableau_field") or x.get("key") for x in old_spec.get("parameters", []) if isinstance(x, dict)}
    new_params = {x.get("tableau_field") or x.get("key") for x in new_spec.get("parameters", []) if isinstance(x, dict)}

    if new_dims - old_dims:
        bullets.append("补回字段：" + "、".join(sorted(new_dims - old_dims)))
    if old_dims - new_dims:
        bullets.append("移除旧字段：" + "、".join(sorted(old_dims - new_dims)))
    if new_measures - old_measures:
        bullets.append("补回指标：" + "、".join(sorted(new_measures - old_measures)))
    if old_measures - new_measures:
        bullets.append("移除旧指标：" + "、".join(sorted(old_measures - new_measures)))
    if new_filters - old_filters:
        bullets.append("补回筛选项：" + "、".join(sorted(new_filters - old_filters)))
    if old_filters - new_filters:
        bullets.append("移除旧筛选：" + "、".join(sorted(old_filters - new_filters)))
    if new_params - old_params:
        bullets.append("补回参数：" + "、".join(sorted(new_params - old_params)))
    if old_params - new_params:
        bullets.append("移除旧参数：" + "、".join(sorted(old_params - new_params)))

    old_sem = old_entry.get("semantics") or {}
    new_sem = new_entry.get("semantics") or {}
    old_metrics = set(old_sem.get("available_metrics") or [])
    new_metrics = set(new_sem.get("available_metrics") or [])
    old_primary_dims = set(old_sem.get("primary_dimensions") or [])
    new_primary_dims = set(new_sem.get("primary_dimensions") or [])
    if new_metrics - old_metrics:
        bullets.append("同步后纳入当前指标语义：" + "、".join(sorted(new_metrics - old_metrics)))
    if old_metrics - new_metrics:
        bullets.append("同步后移出旧指标语义：" + "、".join(sorted(old_metrics - new_metrics)))
    if new_primary_dims - old_primary_dims:
        bullets.append("同步后纳入当前维度语义：" + "、".join(sorted(new_primary_dims - old_primary_dims)))
    if old_primary_dims - new_primary_dims:
        bullets.append("同步后移出旧维度语义：" + "、".join(sorted(old_primary_dims - new_primary_dims)))
    return bullets


def build_source(key: str, current_payload: dict[str, Any], before_enrich_payload: dict[str, Any], before_sync_payload: dict[str, Any]) -> dict[str, Any]:
    entry = current_payload.get("entry") or {}
    spec = current_payload.get("spec") or {}
    before_enrich_spec = before_enrich_payload.get("spec") or {}
    modified: list[dict[str, Any]] = []
    unchanged: list[dict[str, Any]] = []

    for bucket_name, current_items, previous_items in [
        ("筛选项", spec.get("filters") or [], before_enrich_spec.get("filters") or []),
        ("参数", spec.get("parameters") or [], before_enrich_spec.get("parameters") or []),
    ]:
        for current in current_items:
            if not isinstance(current, dict):
                continue
            previous = match_item(previous_items, current)
            label = current.get("tableau_field") or current.get("key") or current.get("display_name") or "未命名"
            record = {
                "类别": bucket_name,
                "名称": label,
                "状态": item_status(current),
                "当前记录": current,
                "修改前记录": previous,
                "带注释记录": annotated_json(current, previous),
            }
            if previous != current:
                modified.append(record)
            else:
                unchanged.append(record)

    need_note = []
    filters = [x for x in spec.get("filters", []) if isinstance(x, dict)]
    params = [x for x in spec.get("parameters", []) if isinstance(x, dict)]
    if sum(1 for x in filters if not x.get("validation")):
        need_note.append(f"仍有 {sum(1 for x in filters if not x.get('validation'))} 个筛选项没有严格校验")
    if sum(1 for x in params if not x.get("validation")):
        need_note.append(f"仍有 {sum(1 for x in params if not x.get('validation'))} 个参数没有严格校验")

    enum_fields = []
    for item in filters + params:
        if isinstance(item.get("validation"), dict) and item["validation"].get("allowed_values_file"):
            enum_fields.append(item.get("tableau_field") or item.get("key") or item.get("display_name"))

    return {
        "数据源": entry.get("display_name") or key,
        "系统内标识": key,
        "说明": entry.get("description") or "暂无说明",
        "最小粒度": (entry.get("semantics") or {}).get("grain") or [],
        "同步阶段": human_sync_summary(before_sync_payload, before_enrich_payload),
        "已修改": modified,
        "未修改": unchanged,
        "枚举字段": enum_fields,
        "待补事项": need_note,
    }


def build_data() -> dict[str, Any]:
    before_sync = load_db(DB_BEFORE_SYNC)
    before_enrich = load_db(DB_BEFORE_ENRICH)
    current = load_db(DB_CURRENT)

    sources = [
        build_source(key, current.get(key, {}), before_enrich.get(key, {}), before_sync.get(key, {}))
        for key in sorted(current.keys())
    ]

    modified_sources = [s for s in sources if s["同步阶段"] or s["已修改"]]
    unchanged_sources = [s for s in sources if not s["同步阶段"] and not s["已修改"]]
    modified_items = sum(len(s["已修改"]) for s in sources)
    unchanged_items = sum(len(s["未修改"]) for s in sources)
    enum_fields = []
    for s in sources:
        for field in s["枚举字段"]:
            enum_fields.append(f'{s["数据源"]}：{field}')

    return {
        "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "统计": {
            "数据源总数": len(sources),
            "有修改的数据源": len(modified_sources),
            "未修改的数据源": len(unchanged_sources),
            "已修改项": modified_items,
            "未修改项": unchanged_items,
        },
        "枚举提示": enum_fields,
        "数据源": sources,
    }


def render_html(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False)
    template = """<!doctype html>
<html lang=\"zh-CN\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>配置变更汇报看板</title>
<style>
:root { --bg:#0b1020; --panel:#121a30; --card:#18233f; --soft:#243357; --text:#eef4ff; --muted:#9fb0d9; --line:#31456f; --good:#59d39b; --warn:#ffb454; --bad:#ff7b72; --blue:#79a8ff; }
*{box-sizing:border-box} body{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;background:radial-gradient(circle at top,#17254a 0,#0b1020 40%,#090d18 100%);color:var(--text)}
.header{padding:24px 28px 16px;border-bottom:1px solid rgba(255,255,255,.08);background:rgba(9,13,24,.75);backdrop-filter:blur(10px);position:sticky;top:0;z-index:5}
.title{font-size:28px;font-weight:800}.sub{margin-top:8px;color:var(--muted);font-size:14px;line-height:1.6}
.wrap{padding:20px 28px 28px}.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}.card{background:linear-gradient(180deg,rgba(255,255,255,.05),rgba(255,255,255,.03));border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:16px;box-shadow:0 10px 30px rgba(0,0,0,.2)}
.num{font-size:30px;font-weight:800;margin-top:6px}.muted{color:var(--muted)}
.notice{margin-top:16px;padding:14px 16px;border-radius:16px;border:1px solid rgba(255,255,255,.08);background:rgba(121,168,255,.09);color:#dce7ff;line-height:1.7}
.layout{display:grid;grid-template-columns:300px 1fr;gap:18px;margin-top:18px}.side,.mainCard{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);border-radius:20px;padding:16px}.side{height:calc(100vh - 240px);overflow:auto;position:sticky;top:156px}
.search{width:100%;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:#0f1730;color:var(--text);outline:none}.list{margin-top:12px;display:grid;gap:8px}.item{width:100%;text-align:left;padding:12px 14px;border-radius:14px;border:1px solid var(--line);background:#101936;color:var(--text);cursor:pointer}.item.active,.item:hover{border-color:var(--blue);background:#16234a}
.main{display:grid;gap:18px}.sectionTitle{font-size:18px;font-weight:800;margin-bottom:12px}.sourceCard{border:1px solid rgba(255,255,255,.08);background:#111a34;border-radius:18px;padding:16px;margin-bottom:16px}.sourceHead{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}.sourceName{font-size:20px;font-weight:800}.badge{display:inline-flex;align-items:center;padding:4px 10px;border-radius:999px;font-size:12px;font-weight:700;margin-right:8px}.b-good{background:rgba(89,211,155,.15);color:#8df0bf}.b-warn{background:rgba(255,180,84,.15);color:#ffd089}.b-blue{background:rgba(121,168,255,.15);color:#bdd3ff}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.panel{background:#0f1730;border:1px solid var(--line);border-radius:16px;padding:14px}.panel h4{margin:0 0 10px;font-size:15px}.panel ul{margin:0;padding-left:18px;color:var(--muted)}.panel li{margin:6px 0}
.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}.chip{padding:6px 10px;border-radius:999px;background:#1b284e;color:#dbe7ff;font-size:12px}.jsonCard{background:#0d152b;border:1px solid var(--line);border-radius:16px;padding:14px;margin-top:12px}.jsonHead{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.jsonTitle{font-weight:700}.status{padding:4px 8px;border-radius:999px;font-size:12px}.status-good{background:rgba(89,211,155,.15);color:#8df0bf}.status-mid{background:rgba(255,180,84,.15);color:#ffd089}.status-new{background:rgba(121,168,255,.15);color:#bdd3ff}
.tableWrap{overflow:auto;border:1px solid var(--line);border-radius:14px;background:#0b1328}.cmpTable{width:100%;border-collapse:collapse;font-size:12px}.cmpTable th,.cmpTable td{padding:10px 12px;border-bottom:1px solid rgba(255,255,255,.06);vertical-align:top;text-align:left}.cmpTable th{position:sticky;top:0;background:#122044;color:#dce7ff}.cmpTable td{color:#d9e4ff}.cmpTable tr:last-child td{border-bottom:none}.fieldCol{min-width:180px;font-weight:700}.valCol{min-width:260px;white-space:pre-wrap;word-break:break-all;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.tag-new{color:#8fc8ff}.tag-changed{color:#ffd089}.tag-same{color:#8df0bf}
pre{margin:0;white-space:pre-wrap;word-break:break-all;color:#e7eeff;font:12px/1.7 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.empty{color:var(--muted);font-size:13px}
.tabs{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.tab{padding:8px 12px;border-radius:999px;border:1px solid var(--line);background:#0f1730;color:var(--text);cursor:pointer}.tab.active{background:#213664;border-color:#6e99ff}
.hidden{display:none}
@media (max-width: 980px){.layout{grid-template-columns:1fr}.side{position:static;height:auto}.cols{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class=\"header\">
  <div class=\"title\">配置变更汇报看板</div>
  <div class=\"sub\">按系统原结构展示。只看两类：哪些改了、哪些没改；改动项用当前值展示，行尾 `#` 后面是修改前。</div>
  <div class=\"sub\">生成时间：__TIME__</div>
</div>
<div class=\"wrap\">
  <div class=\"summary\" id=\"summary\"></div>
  <div class=\"notice\" id=\"notice\"></div>
  <div class=\"layout\">
    <div class=\"side\">
      <input class=\"search\" id=\"search\" placeholder=\"搜表名、字段、改动内容\" />
      <div class=\"list\" id=\"sourceList\"></div>
    </div>
    <div class=\"main\">
      <div class=\"mainCard\">
        <div class=\"sectionTitle\">汇报内容</div>
        <div class=\"toolbar\">
          <span class=\"chip\">枚举信息只在顶部统一提示</span>
          <span class=\"chip\">修改项默认显示前后对比表</span>
          <span class=\"chip\">下方保留当前记录 + 修改前注释</span>
        </div>
        <div id=\"content\"></div>
      </div>
    </div>
  </div>
</div>
<script>
const DATA = __DATA__;
let active = '全部';
let keyword = '';
let tabMode = 'all';
function h(v){return String(v||'').replace(/[&<>\"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}[s]));}
function renderSummary(){const box=document.getElementById('summary'); box.innerHTML = Object.entries(DATA['统计']).map(([k,v])=>`<div class=\"card\"><div class=\"muted\">${h(k)}</div><div class=\"num\">${h(v)}</div></div>`).join('');}
function renderNotice(){const enums = DATA['枚举提示']||[]; const text = enums.length ? '顶部特殊枚举字段：'+enums.join('；') : '顶部特殊枚举字段：本次没有新增特别枚举说明'; document.getElementById('notice').innerHTML = text;}
function sourceMatch(src){ if(!keyword) return true; return JSON.stringify(src).includes(keyword); }
function renderSourceList(){ const list=document.getElementById('sourceList'); const rows=DATA['数据源'].filter(sourceMatch); const html=[`<button class=\"item ${active==='全部'?'active':''}\" data-name=\"全部\">全部数据源</button>`].concat(rows.map(s=>`<button class=\"item ${active===s['数据源']?'active':''}\" data-name=\"${h(s['数据源'])}\">${h(s['数据源'])}</button>`)); list.innerHTML = html.join(''); list.querySelectorAll('button').forEach(btn=>btn.onclick=()=>{active=btn.dataset.name; renderContent(); renderSourceList();}); }
function asText(v){ if(v===undefined || v===null) return '无'; if(typeof v==='object') return JSON.stringify(v, null, 2); return String(v); }
function diffRows(current, previous, prefix=''){ const keys = Array.from(new Set([...Object.keys(previous||{}), ...Object.keys(current||{})])); let rows=[]; keys.forEach(key=>{ const path = prefix ? `${prefix}.${key}` : key; const cur = current ? current[key] : undefined; const prev = previous ? previous[key] : undefined; if(cur && typeof cur === 'object' && !Array.isArray(cur)){ rows = rows.concat(diffRows(cur, prev||{}, path)); } else { let status = '未变'; if(prev === undefined) status = '新增'; else if(JSON.stringify(cur)!==JSON.stringify(prev)) status = '已改'; rows.push({字段:path, 修改前:asText(prev), 修改后:asText(cur), 状态:status}); } }); return rows; }
function compareTable(item){ const rows = diffRows(item['当前记录']||{}, item['修改前记录']||{}); return `<div class=\"tableWrap\"><table class=\"cmpTable\"><thead><tr><th class=\"fieldCol\">字段</th><th>修改前</th><th>修改后</th><th>状态</th></tr></thead><tbody>${rows.map(r=>`<tr><td class=\"fieldCol\">${h(r['字段'])}</td><td class=\"valCol\">${h(r['修改前'])}</td><td class=\"valCol\">${h(r['修改后'])}</td><td>${r['状态']==='新增'?'<span class=\"tag-new\">新增</span>':r['状态']==='已改'?'<span class=\"tag-changed\">已改</span>':'<span class=\"tag-same\">未变</span>'}</td></tr>`).join('')}</tbody></table></div>`; }
function compareCard(item){ return `<div class=\"jsonCard\"><div class=\"jsonHead\"><div class=\"jsonTitle\">${h(item['类别'])}：${h(item['名称'])}</div><div class=\"status ${item['状态']==='已补规则'?'status-good':item['状态']==='已补结构'?'status-new':'status-mid'}\">${h(item['状态'])}</div></div>${compareTable(item)}<div style=\"margin-top:10px\"><pre>${h(item['带注释记录'])}</pre></div></div>`; }
function sourceBlock(src){ const changed = src['已修改']; const unchanged = src['未修改']; const sync = src['同步阶段']; const todo = src['待补事项']; const showChanged = tabMode==='all' || tabMode==='changed'; const showUnchanged = tabMode==='all' || tabMode==='unchanged'; const showSync = tabMode==='all' || tabMode==='sync'; return `
<div class=\"sourceCard\">
  <div class=\"sourceHead\">
    <div>
      <div class=\"sourceName\">${h(src['数据源'])}</div>
      <div class=\"muted\" style=\"margin-top:6px\">系统内标识：${h(src['系统内标识'])}</div>
      <div class=\"muted\" style=\"margin-top:6px\">${h(src['说明'])}</div>
    </div>
    <div>
      <span class=\"badge b-good\">已修改 ${changed.length}</span>
      <span class=\"badge b-blue\">未修改 ${unchanged.length}</span>
      <span class=\"badge b-warn\">同步变更 ${sync.length}</span>
    </div>
  </div>
  <div class=\"cols\">
    <div class=\"panel\"><h4>整体状态</h4><ul><li>最小粒度：${src['最小粒度'].length? h(src['最小粒度'].join('、')):'暂无'}</li>${todo.map(x=>`<li>${h(x)}</li>`).join('') || '<li>结构补齐已完成</li>'}</ul></div>
    <div class=\"panel\"><h4>未修改项</h4>${unchanged.length? `<div class=\"toolbar\">${unchanged.map(x=>`<span class=\"chip\">${h(x['类别'])}：${h(x['名称'])}</span>`).join('')}</div>`:'<div class=\"empty\">无</div>'}</div>
  </div>
  ${showSync ? `<div class=\"panel\" style=\"margin-top:14px\"><h4>同步阶段改动</h4>${sync.length? `<ul>${sync.map(x=>`<li>${h(x)}</li>`).join('')}</ul>`:'<div class=\"empty\">无</div>'}</div>` : ''}
  ${showChanged ? `<div style=\"margin-top:14px\">${changed.length? changed.map(compareCard).join('') : '<div class=\"empty\">无修改项</div>'}</div>` : ''}
  ${showUnchanged && !showChanged ? `<div style=\"margin-top:14px\">${unchanged.length? unchanged.map(x=>`<div class=\"jsonCard\"><div class=\"jsonHead\"><div class=\"jsonTitle\">${h(x['类别'])}：${h(x['名称'])}</div><div class=\"status status-good\">未修改</div></div><pre>${h(JSON.stringify(x['当前记录'], null, 2))}</pre></div>`).join('') : '<div class=\"empty\">无未修改项</div>'}</div>` : ''}
</div>`; }
function renderContent(){ const box=document.getElementById('content'); let rows=DATA['数据源'].filter(sourceMatch); if(active!=='全部') rows = rows.filter(x=>x['数据源']===active); const tabs=`<div class=\"tabs\"><button class=\"tab ${tabMode==='all'?'active':''}\" data-tab=\"all\">全部</button><button class=\"tab ${tabMode==='changed'?'active':''}\" data-tab=\"changed\">只看已修改</button><button class=\"tab ${tabMode==='unchanged'?'active':''}\" data-tab=\"unchanged\">只看未修改</button><button class=\"tab ${tabMode==='sync'?'active':''}\" data-tab=\"sync\">只看同步阶段</button></div>`; box.innerHTML = tabs + (rows.length ? rows.map(sourceBlock).join('') : '<div class=\"empty\">没有匹配的数据源</div>'); box.querySelectorAll('.tab').forEach(btn=>btn.onclick=()=>{tabMode=btn.dataset.tab; renderContent();}); }
document.getElementById('search').addEventListener('input',e=>{keyword=e.target.value.trim(); renderSourceList(); renderContent();});
renderSummary(); renderNotice(); renderSourceList(); renderContent();
</script>
</body>
</html>"""
    return template.replace("__DATA__", data_json).replace("__TIME__", data["生成时间"])


def main() -> None:
    data = build_data()
    OUT_HTML.write_text(render_html(data), encoding="utf-8")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
