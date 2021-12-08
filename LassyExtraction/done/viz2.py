import graphviz as gv
from .graphutils2 import DAG


def render(dag: DAG[str], **kwargs) -> None:
    Renderer.render(dag, **kwargs)


class Renderer:
    properties = ('id', 'word', 'pos', 'cat', 'index', 'type', 'pt')

    @staticmethod
    def make_node_label(node: dict) -> str:
        return '\n'.join(f'{prop}: {node[prop]}' for prop in Renderer.properties if prop in node.keys())

    @staticmethod
    def make_html_label(node: dict) -> str:
        return '<' + '<br/>'.join(f'<b>{k}</b>: {node[k]}' for k in Renderer.properties if k in node.keys()) + '>'

    @staticmethod
    def render(dag: DAG, **kwargs) -> None:
        graph = gv.Digraph()
        for node in dag.nodes:
            graph.node(node, label=Renderer.make_html_label(dag.attribs[node]),
                       _attributes={'shape': 'rectangle', 'color': 'gray'})
        for edge in dag.edges:
            graph.edge(edge.source, edge.target, label=edge.label)
        graph.render(view=True, **kwargs)
