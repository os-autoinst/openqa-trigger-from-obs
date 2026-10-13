import io
from xml.etree import ElementTree

from script.scriptgen import ActionBatch, ActionGenerator


def make_batch() -> ActionBatch:
    ag = ActionGenerator(
        envdir="/tmp",
        project="openSUSE:Factory:Staging:J",
        productpath="",
        version="Factory",
        brand="obs",
    )
    # normally set by doFile(), needed by p()
    ag.iso_path = ""
    ag.repo_path = "repo"
    ag.domain = ""
    return ActionBatch("default", ag)


def test_default_rsync_timeout_is_3600():
    batch = make_batch()
    assert batch.rsync_timeout == "3600"


def test_batch_node_rsynctimeout_sets_batch_timeout():
    ag = ActionGenerator(
        envdir="/tmp",
        project="openSUSE:Factory:Staging:J",
        productpath="",
        version="Factory",
        brand="obs",
    )
    ag.iso_path = ""
    ag.repo_path = "repo"
    ag.domain = ""
    ag.doBatch(ElementTree.fromstring('<batch name="custom" rsynctimeout="7200"/>'))
    batch = ag.batches[0]
    assert batch.rsync_timeout == "7200"


def test_root_node_rsynctimeout_overrides_default_timeout():
    ag = ActionGenerator(
        envdir="/tmp",
        project="openSUSE:Factory:Staging:J",
        productpath="",
        version="Factory",
        brand="obs",
    )
    ag.iso_path = ""
    ag.repo_path = "repo"
    ag.domain = ""
    ag.doBatch(ElementTree.fromstring('<openQA name="x" rsynctimeout="7200"/>'))
    batch = ag.batches[0]
    assert batch.rsync_timeout == "7200"


def test_root_node_rsynctimeout_inherits_to_batches_in_dofile(tmp_path):
    xml = """<openQA rsynctimeout="7200">
        <batch name="b1"/>
        <batch name="b2" rsynctimeout="1800"/>
    </openQA>"""
    xmlfile = tmp_path / "project.xml"
    xmlfile.write_text(xml)
    ag = ActionGenerator(
        envdir=str(tmp_path),
        project="openSUSE:Factory:Staging:J",
        productpath="",
        version="Factory",
        brand="obs",
    )
    ag.doFile(str(xmlfile))
    assert ag.rsync_timeout == "7200"
    assert ag.batches[0].rsync_timeout == "7200"
    assert ag.batches[1].rsync_timeout == "1800"


def test_p_substitutes_default_rsync_timeout():
    batch = make_batch()
    out = io.StringIO()
    batch.p('echo "time rsync --timeout=RSYNCTIMEOUT -tlp4"', out)
    assert out.getvalue() == 'echo "time rsync --timeout=3600 -tlp4"\n'


def test_p_substitutes_custom_rsync_timeout():
    batch = make_batch()
    batch.rsync_timeout = "7200"
    out = io.StringIO()
    batch.p('echo "time rsync --timeout=RSYNCTIMEOUT -tlp4"', out)
    assert out.getvalue() == 'echo "time rsync --timeout=7200 -tlp4"\n'


def test_p_allows_explicit_override_in_extra_args():
    batch = make_batch()
    batch.rsync_timeout = "7200"
    out = io.StringIO()
    batch.p(
        'echo "time rsync --timeout=RSYNCTIMEOUT -tlp4"',
        out,
        "RSYNCTIMEOUT",
        "1800",
    )
    assert out.getvalue() == 'echo "time rsync --timeout=1800 -tlp4"\n'


BATCH_TIMEOUT_XML = """<openQA archs="x86_64" dist_path="images/x86_64">
    <batch name="dvd" folder="*product*" rsynctimeout="5400">
        <flavor name="DVD" distri="opensuse" iso="1"/>
    </batch>
</openQA>"""

NO_TIMEOUT_XML = """<openQA archs="x86_64" dist_path="images/x86_64">
    <batch name="dvd" folder="*product*">
        <flavor name="DVD" distri="opensuse" iso="1"/>
    </batch>
</openQA>"""

ROOT_TIMEOUT_XML = """<openQA archs="x86_64" dist_path="images/x86_64" rsynctimeout="4800">
    <flavor name="DVD" distri="opensuse" iso="1" folder="*product*"/>
</openQA>"""

ROOT_AND_BATCH_TIMEOUT_XML = """<openQA archs="x86_64" dist_path="images/x86_64" rsynctimeout="4800">
    <batch name="dvd" folder="*product*" rsynctimeout="5400">
        <flavor name="DVD" distri="opensuse" iso="1"/>
    </batch>
</openQA>"""


def generate(tmp_path, xml, generator="gen_print_rsync_iso"):
    xmlfile = tmp_path / "project.xml"
    xmlfile.write_text(xml)
    ag = ActionGenerator(
        envdir=str(tmp_path),
        project="openSUSE:Factory:Staging:J",
        productpath="images/x86_64",
        version="Factory",
        brand="obs",
    )
    ag.doFile(str(xmlfile))
    out = io.StringIO()
    for batch in ag.batches:
        getattr(batch, generator)(out)
    return out.getvalue()


def test_generated_script_uses_batch_rsynctimeout(tmp_path):
    script = generate(tmp_path, BATCH_TIMEOUT_XML)
    assert "--timeout=5400" in script
    assert "--timeout=3600" not in script
    assert "RSYNCTIMEOUT" not in script


def test_generated_script_uses_default_rsynctimeout_when_omitted(tmp_path):
    script = generate(tmp_path, NO_TIMEOUT_XML)
    assert "--timeout=3600" in script
    assert "RSYNCTIMEOUT" not in script


def test_generated_script_uses_root_rsynctimeout(tmp_path):
    script = generate(tmp_path, ROOT_TIMEOUT_XML)
    assert "--timeout=4800" in script
    assert "--timeout=3600" not in script
    assert "RSYNCTIMEOUT" not in script


def test_generated_script_batch_overrides_root_rsynctimeout(tmp_path):
    script = generate(tmp_path, ROOT_AND_BATCH_TIMEOUT_XML)
    assert "--timeout=5400" in script
    assert "--timeout=4800" not in script
    assert "RSYNCTIMEOUT" not in script
