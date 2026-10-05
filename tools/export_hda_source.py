"""Export full VEX, parameter interface and node connections from the bundled HDA.
Run with Houdini's hython: hython tools/export_hda_source.py [repository_root]
The HDA definition is read without saving changes to it.
"""
import hashlib
import json
import pathlib
import sys
import hou

root = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1]
hda = root / 'hda' / 'object_REX.dev.HDA_BlockStack_Building_V2.2.0.hda'
hou.hda.installFile(str(hda))
asset = hou.node('/obj').createNode('REX::dev::HDA_BlockStack_Building_V2::2.0', 'SOURCE_EXPORT')
definition = asset.type().definition()
(root / 'vex').mkdir(parents=True, exist_ok=True)
(root / 'hda' / 'parameter_interface.ds').write_text(definition.parmTemplateGroup().asDialogScript(), encoding='utf-8')
node_manifest = []
source_files = []
for node in sorted(asset.allSubChildren(), key=lambda n: n.path()):
    relative = node.path()[len(asset.path()) + 1:]
    entry = {'path': relative, 'type': node.type().name(), 'category': node.type().category().name(), 'inputs': []}
    for connection in node.inputConnections():
        upstream = connection.inputNode()
        connection_info = {'input_index': connection.inputIndex(), 'source': upstream.path()[len(asset.path()) + 1:] if upstream else None, 'source_output_index': connection.outputIndex()}
        if upstream is None:
            indirect_method = getattr(connection, 'subnetIndirectInput', None)
            indirect = indirect_method() if indirect_method else None
            connection_info['subnet_input_index'] = indirect.number() if indirect is not None else None
        entry['inputs'].append(connection_info)
    snippet = node.parm('snippet')
    if snippet:
        text = snippet.evalAsString()
        filename = relative.replace('/', '__') + '.vfl'
        (root / 'vex' / filename).write_bytes(text.encode('utf-8'))
        entry['vex_file'] = 'vex/' + filename
        try:
            entry['run_over'] = {'value': node.parm('class').eval(), 'label': node.parm('class').evalAsString()}
        except Exception:
            pass
        source_files.append({'node': relative, 'file': entry['vex_file'], 'bytes': len(text.encode('utf-8')), 'lines': len(text.splitlines()), 'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()})
    node_manifest.append(entry)
parameters = []
for parameter in asset.parms():
    template = parameter.parmTemplate()
    if template.type() in (hou.parmTemplateType.Button, hou.parmTemplateType.Separator, hou.parmTemplateType.Label):
        continue
    item = {'name': parameter.name(), 'label': template.label(), 'type': str(template.type())}
    try:
        item['value'] = parameter.unexpandedString() if template.type() == hou.parmTemplateType.String else parameter.eval()
    except Exception as error:
        item['read_error'] = str(error)
    parameters.append(item)
sections = [{'name': name, 'bytes': len(section.contents().encode('utf-8', errors='replace'))} for name, section in definition.sections().items()]
(root / 'hda' / 'node_manifest.json').write_text(json.dumps(node_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
(root / 'hda' / 'parameter_defaults.json').write_text(json.dumps(parameters, ensure_ascii=False, indent=2), encoding='utf-8')
manifest = {'asset_type': asset.type().name(), 'houdini_version': hou.applicationVersionString(), 'scripts': len(source_files), 'raw_lines': sum(s['lines'] for s in source_files), 'hda_sha256': hashlib.sha256(hda.read_bytes()).hexdigest(), 'definition_sections': sections, 'files': source_files}
(root / 'source_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps({'scripts': len(source_files), 'network_nodes': len(node_manifest), 'parameters': len(parameters), 'sections': [s['name'] for s in sections]}))
