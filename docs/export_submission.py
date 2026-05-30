"""
生成课程提交用 PDF/PPTX 文件
运行：python -X utf8 docs/export_submission.py
输出：
  - docs/课程PPT.pptx
  - report.pdf（若环境支持 pandoc）
  - slides.pdf（若环境支持 pandoc）
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"


def run_gen_ppt():
    print("[1/3] 生成 PPT...")
    subprocess.check_call([sys.executable, "-X", "utf8", str(DOCS / "gen_ppt.py")], cwd=ROOT)
    pptx = DOCS / "课程PPT.pptx"
    if not pptx.exists():
        raise FileNotFoundError(f"未生成: {pptx}")
    print(f"  ✅ {pptx}")


def try_pandoc_export():
    """尝试用 pandoc 导出 PDF；失败时给出手动说明。"""
    report_md = DOCS / "课程报告.md"
    report_pdf = ROOT / "report.pdf"
    slides_pptx = DOCS / "课程PPT.pptx"
    slides_pdf = ROOT / "slides.pdf"

    try:
        import pypandoc
    except ImportError:
        print("[2/3] 跳过 report.pdf：未安装 pypandoc（可选 pip install pypandoc）")
        print("      请用 Word / WPS 打开 docs/课程报告.md 另存为 report.pdf")
        return False

    try:
        print("[2/3] 导出 report.pdf（pandoc）...")
        pypandoc.convert_file(
            str(report_md),
            "pdf",
            outputfile=str(report_pdf),
            extra_args=["--pdf-engine=xelatex", "-V", "CJKmainfont=SimSun"],
        )
        print(f"  ✅ {report_pdf}")
    except Exception as e:
        print(f"  ⚠️ report.pdf 导出失败: {e}")
        print("      请手动：Word 打开 docs/课程报告.md → 另存为 report.pdf")
        return False

    if slides_pptx.exists():
        try:
            print("[3/3] 导出 slides.pdf（pandoc）...")
            pypandoc.convert_file(str(slides_pptx), "pdf", outputfile=str(slides_pdf))
            print(f"  ✅ {slides_pdf}")
        except Exception as e:
            print(f"  ⚠️ slides.pdf 导出失败: {e}")
            print("      请手动：PowerPoint 打开 docs/课程PPT.pptx → 另存为 slides.pdf")
    return True


def copy_pptx_to_root():
    src = DOCS / "课程PPT.pptx"
    if src.exists():
        dst = ROOT / "slides.pptx"
        shutil.copy2(src, dst)
        print(f"  ✅ 已复制到 {dst}")


def main():
    run_gen_ppt()
    copy_pptx_to_root()
    try_pandoc_export()
    print("\n提交前请确认：")
    print("  - report.pdf（根目录或按组号重命名）")
    print("  - slides.pptx / slides.pdf")
    print("  - 运行 python -X utf8 run_all.py --simulate 生成 results/")


if __name__ == "__main__":
    main()
