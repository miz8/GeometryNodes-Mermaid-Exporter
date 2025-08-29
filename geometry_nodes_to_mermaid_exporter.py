import bpy
from bpy_extras.io_utils import ExportHelper
from bpy.props import EnumProperty

bl_info = {
    "name": "Geometry Nodes Tree to Mermaid",
    "author": "miz8",
    "version": (1, 0, 1),
    "blender": (4, 0, 0),
    "location": "F3 Search Menu",
    "description": "Exports a Geometry Nodes tree as a Mermaid graph markdown file.",
    "warning": "",
    "doc_url": "https://github.com/miz8/GeometryNodes-Mermaid-Exporter",
    "category": "Import-Export",
}


def get_node_tree_mermaid(node_tree, file_format):
    """
    Generate a Mermaid graph definition for a given Geometry Nodes tree,
    including styles for custom-colored nodes and link labels for Group I/O,
    while excluding disconnected nodes.

    Args:
        node_tree (bpy.types.NodeTree): The Geometry Nodes tree to convert.
        file_format (str): The desired file format ('md' or 'html').

    Returns:
        str: A string containing the Mermaid graph definition with styles and link labels.
    """
    nodes = node_tree.nodes
    links = node_tree.links

    connected_nodes = set()
    for link in links:
        connected_nodes.add(link.from_node.name)
        connected_nodes.add(link.to_node.name)

    frames = [n for n in nodes if n.bl_idname == 'NodeFrame']
    frame_nodes = {}
    for frame in frames:
        frame_nodes[frame.name] = []

    for node in nodes:
        if node.parent and node.parent.bl_idname == 'NodeFrame':
            frame_nodes[node.parent.name].append(node)

    mermaid_lines = []
    if file_format == 'md':
        mermaid_lines.append("```mermaid")

    mermaid_lines.append("graph TD")

    node_map = {}

    for frame in frames:
        if frame.name not in frame_nodes or not frame_nodes[frame.name]:
            continue

        has_connected_child = any(n.name in connected_nodes for n in frame_nodes[frame.name])
        if not has_connected_child:
            continue

        frame_label = frame.label if frame.label else frame.name
        mermaid_lines.append(f"    subgraph {frame_label}")

        for i, node in enumerate(frame_nodes[frame.name]):
            if node.name in connected_nodes:
                node_id = f"{node.parent.name}_{node.name}".replace(" ", "_")
                node_map[node.name] = node_id
                label = node.label if node.label else node.bl_label
                mermaid_lines.append(f"        {node_id}[{label}]")

        mermaid_lines.append("    end")

    for i, node in enumerate(nodes):
        if not node.parent and node.name in connected_nodes:
            node_id = f"node_{i}"
            node_map[node.name] = node_id
            label = node.label if node.label else node.bl_label
            mermaid_lines.append(f"    {node_id}[{label}]")

    for link in links:
        from_node_id = node_map.get(link.from_node.name)
        to_node_id = node_map.get(link.to_node.name)

        link_label = ""
        if link.from_node.bl_idname == 'NodeGroupInput':
            link_label = link.from_socket.name
        elif link.to_node.bl_idname == 'NodeGroupOutput':
            link_label = link.to_socket.name

        if from_node_id and to_node_id:
            if link_label:
                mermaid_lines.append(f"    {from_node_id} --> |{link_label}| {to_node_id}")
            else:
                mermaid_lines.append(f"    {from_node_id} --> {to_node_id}")

    for i, node in enumerate(nodes):
        if node.name in connected_nodes and node.use_custom_color:
            node_id = node_map.get(node.name)
            if node_id:
                # Blender 4.0以降の色取得方法に対応
                color = node.color
                r = int(color[0] * 255)
                g = int(color[1] * 255)
                b = int(color[2] * 255)
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                mermaid_lines.append(f"    style {node_id} fill:{hex_color},stroke:#333")

    if file_format == 'md':
        mermaid_lines.append("```")
    return "\n".join(mermaid_lines)


class EXPORT_OT_export_mermaid(bpy.types.Operator, ExportHelper):
    """
    Export the active object's Geometry Nodes tree as a Mermaid graph.
    """
    bl_idname = "export.export_mermaid"
    bl_label = "Export Geometry Nodes Tree to Mermaid"
    bl_options = {'REGISTER'}

    filename_ext: bpy.props.StringProperty(
        name="File Extension",
        options={'HIDDEN'},
    )
    filter_glob: bpy.props.StringProperty(
        default="*.md;*.html",
        options={'HIDDEN'},
    )
    file_format: EnumProperty(
        name="Format",
        items=(
            ('md', "Markdown", "Export as a Markdown file with a Mermaid code block"),
            ('html', "HTML", "Export as a html file")
        ),
        default='md',
    )

    def execute(self, context):
        """
        Main execution method for the operator.
        """
        print(f"Filepath: {self.filepath}")
        obj = context.active_object
        if not obj or not obj.modifiers:
            self.report({'WARNING'}, "No active object or no modifiers found.")
            return {'CANCELLED'}

        geo_nodes_modifier = None
        for mod in obj.modifiers:
            if mod.type == 'NODES':
                geo_nodes_modifier = mod
                break

        if not geo_nodes_modifier or not geo_nodes_modifier.node_group:
            self.report({'WARNING'}, "No Geometry Nodes modifier found on the active object.")
            return {'CANCELLED'}

        mermaid_code = get_node_tree_mermaid(geo_nodes_modifier.node_group, self.file_format)

        filepath = self.filepath
        if self.file_format == 'md' and not filepath.endswith('.md'):
            filepath += '.md'
        elif self.file_format == 'html' and not filepath.endswith('.html'):
            mermaid_code = r"""
            <!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <title>Mermaid Demo</title>
  <script src="https://unpkg.com/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
  <div class="mermaid">
  """ + mermaid_code + r"""
    </div>

  <script>
    mermaid.initialize({
      startOnLoad: true
    });
  </script>
</body>
</html>
  """
            filepath += '.html'

        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(mermaid_code)
            self.report({'INFO'}, f"Successfully exported to {filepath}")
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(EXPORT_OT_export_mermaid.bl_idname)


classes = [EXPORT_OT_export_mermaid]


def register():
    """
    Register the classes.
    """
    for i in classes:
        bpy.utils.register_class(i)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    """
    Unregister the classes.
    """
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    for i in classes:
        bpy.utils.unregister_class(i)


if __name__ == "__main__":
    register()
