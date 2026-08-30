"""XMP边车文件。

筛片结果必须回到用户已有的工作流里才有意义。Lightroom、Capture One、
Bridge、digiKam都读同名的.xmp边车，写星级和色标进去，用户在自己习惯的
软件里按星级过滤即可，不需要学新工具，也不需要移动文件。

原始文件一个字节都不改。已存在的xmp只更新星级、色标和说明三个字段，
其余内容原样保留，避免覆盖用户已有的关键词、镜头校正等编辑信息。
"""

import os
import re
import tempfile
from xml.sax import saxutils

LABEL_NAMES = {
    "red": "Red",
    "yellow": "Yellow",
    "green": "Green",
    "blue": "Blue",
    "purple": "Purple",
    "": "",
}

TEMPLATE = """<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="photo-cull">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmp:Rating="{rating}"
   xmp:Label="{label}">
   <dc:description>
    <rdf:Alt>
     <rdf:li xml:lang="x-default">{note}</rdf:li>
    </rdf:Alt>
   </dc:description>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
"""


def sidecar_path(image_path):
    return os.path.splitext(image_path)[0] + ".xmp"


def write(image_path, rating, label, note="", dry_run=False):
    path = sidecar_path(image_path)
    label_name = LABEL_NAMES.get(str(label).lower(), str(label))
    note = saxutils.escape(note or "")[:900]

    if os.path.exists(path):
        content = _patch_existing(path, rating, label_name, note)
    else:
        content = TEMPLATE.format(rating=int(rating), label=label_name, note=note)

    if not dry_run:
        directory = os.path.dirname(os.path.abspath(path)) or "."
        os.makedirs(directory, exist_ok=True)
        fd, temporary = tempfile.mkstemp(
            prefix=f".{os.path.basename(path)}.", suffix=".tmp", dir=directory
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(content)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
    return path


def _patch_existing(path, rating, label_name, note):
    """只替换三个字段，保留用户已有的关键词与编辑记录。"""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        content = fh.read()

    def set_attr(text, key, value):
        pattern = re.compile(rf'{re.escape(key)}\s*=\s*"[^"]*"')
        if pattern.search(text):
            return pattern.sub(f'{key}="{value}"', text, count=1)
        return re.sub(
            r"(<rdf:Description\b[^>]*?)(/?>)",
            rf'\1\n   {key}="{value}"\2',
            text,
            count=1,
        )

    content = set_attr(content, "xmp:Rating", int(rating))
    content = set_attr(content, "xmp:Label", label_name)
    if note:
        if "<dc:description>" in content:
            content = re.sub(
                r'(<rdf:li xml:lang="x-default">)(.*?)(</rdf:li>)',
                rf"\g<1>{note}\g<3>",
                content,
                count=1,
                flags=re.DOTALL,
            )
    return content


def remove(image_path, dry_run=False):
    path = sidecar_path(image_path)
    if os.path.exists(path) and not dry_run:
        os.remove(path)
    return path
