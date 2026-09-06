"""Stage existing clay renders and GLBs for local comparison; no API calls."""
from pathlib import Path
import hashlib
import html
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".meshy/geometry-comparison"
OUTPUT = ROOT / "public/assets/review/general_red/geometry-comparison"
ITEMS = (
    ("agent-benchmark", "官网 Agent · 几何基准", "完整披风、底座和服饰结构；由用户提供。"),
    ("api-v1-high", "旧 API · 原始高模", "长披风和底座缺失；这是减面前的原件。"),
    ("api-v2-ultra", "新 API · Ultra 高模", "披风不完整、底座缺失，珠串和靴子有缺陷；不合格。"),
)
VIEWS = ("front", "three_quarter", "back", "detail")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    cards, metadata = [], []
    for key, title, note in ITEMS:
        report = json.loads((SOURCE / key / "geometry.json").read_text(encoding="utf-8"))
        model = Path(report["input"])
        assert model.is_relative_to(ROOT), "Only project models can be staged"
        assert hashlib.sha256(model.read_bytes()).hexdigest() == report["sha256"], "Model changed after render"
        assert report["geometry_modified"] is False and report["texture_or_normal_map_used"] is False
        target = OUTPUT / key
        target.mkdir(exist_ok=True)
        for view in VIEWS:
            shutil.copy2(SOURCE / key / f"{view}.png", target / f"{view}.png")
        shutil.copy2(model, target / "model.glb")
        metadata.append({"id": key, "title": title, "triangles": report["triangles"], "sha256": report["sha256"]})
        cards.append(f'''<article><h2>{html.escape(title)}</h2>
<p class="count">{report['triangles']:,} 三角面</p>
<a class="render" href="{key}/front.png" target="_blank" rel="noreferrer"><img data-model="{key}" src="{key}/front.png" alt="{html.escape(title)}的正面素模渲染"></a>
<p>{html.escape(note)}</p><a href="{key}/model.glb" download>下载原始 GLB</a></article>''')
    document = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>红帅 · 原始高模对比</title><link rel="icon" href="data:,"><style>
*{box-sizing:border-box}body{margin:0;background:#101718;color:#ebede8;font:16px/1.6 system-ui,"Microsoft YaHei",sans-serif}main{max-width:1560px;margin:auto;padding:26px}h1{font-size:30px;margin:6px 0}h2{font-size:20px;margin:12px 0 0}.intro,.count{color:#b8c1bb}.count{margin:0 0 14px}nav{display:flex;gap:10px;flex-wrap:wrap;margin:22px 0}button{font:inherit;padding:8px 22px;border:1px solid #6e7c74;border-radius:6px;background:#1a2525;color:#ebede8;cursor:pointer}button[aria-pressed=true]{background:#dbbd82;color:#161d1c}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}article{background:#192324;padding:16px;border-radius:10px}img{display:block;width:100%;aspect-ratio:5/6;object-fit:contain;background:#101718}article p{margin:12px 0}a{color:#e1c38b}footer{margin:24px 0;color:#bbc3bf}code{overflow-wrap:anywhere}@media(max-width:760px){main{padding:16px}.cards{grid-template-columns:1fr}h1{font-size:25px}}
</style></head><body><main><p class="intro">红方 · 帅 / 2026-09-05</p><h1>后续几何，以官网高模为基准</h1><p class="intro">三份真实 GLB 使用同一素模材质、光照和相机。整体等高居中，仅为展示缩放，没有减面、修形或使用贴图。点击图片可放大检查。</p><nav aria-label="对比视角"><button data-view="front" aria-pressed="true">正面</button><button data-view="three_quarter" aria-pressed="false">45°</button><button data-view="back" aria-pressed="false">背面</button><button data-view="detail" aria-pressed="false">细节</button></nav><section class="cards">''' + "".join(cards) + '''</section><footer><p>结论：Ultra 的面数已接近基准，但造型仍未达标。旧版材质效果可以继续作为贴图标准；不从未通过的几何开始批量。</p><p>本项目两次 API 任务累计 60 积分（旧版 35 + 本次 25），本次完成后余额 3005。官网原件不计入本项目两笔调用。</p><a href="/review.html">查看旧版贴图样板</a></footer></main><script>
const labels={front:'正面',three_quarter:'45°',back:'背面',detail:'细节'};
document.querySelectorAll('button[data-view]').forEach(button=>button.addEventListener('click',()=>{
 document.querySelectorAll('button[data-view]').forEach(item=>item.setAttribute('aria-pressed',String(item===button)));
 document.querySelectorAll('img[data-model]').forEach(img=>{img.src=img.dataset.model+'/'+button.dataset.view+'.png';img.alt=img.closest('article').querySelector('h2').textContent+'的'+labels[button.dataset.view]+'素模渲染';img.parentElement.href=img.src;});
}));
</script></body></html>'''
    document = document.replace(
        '本项目两次 API 任务累计 60 积分（旧版 35 + 本次 25），本次完成后余额 3005。官网原件不计入本项目两笔调用。',
        '几何对照两笔合计 60 积分；随后给官网原件上贴图花费 15，项目累计 75，余额 2990。')
    document = document.replace('<a href="/review.html">查看旧版贴图样板</a>',
        '<a href="/master-review.html">查看完整官网高模的最新贴图样板 →</a> · <a href="/review.html">旧版记录</a>')
    (OUTPUT / "index.html").write_text(document, encoding="utf-8")
    (OUTPUT / "manifest.json").write_text(json.dumps({"models": metadata, "api_quality_accepted": False}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Staged three original GLBs and twelve renders; no credentials or task URLs included.")


if __name__ == "__main__":
    main()
