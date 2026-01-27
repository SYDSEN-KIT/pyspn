from graphviz import Digraph
from .spn import *

def _count_in_service(t: Transition) -> int:
    """How many tokens are currently reserved inside this transition (parallel timing)."""
    if not getattr(t, "parallel_timing", False):
        return 0
    if not hasattr(t, "pt_instances") or t.pt_instances is None:
        return 0
    return sum(len(inst.get("tokens", [])) for inst in t.pt_instances)

def draw_spn(spn: SPN, file="spn_default", show=True, print_place_labels=False, rankdir="TB"):
    if rankdir == "TB":
        spn_graph = Digraph(engine="dot")
    else:
        spn_graph = Digraph(engine="dot", graph_attr={'rankdir': 'LR'})

    # --- NEW: compute "in service" tokens per INPUT place for parallel timed transitions ---
    reserved_for_place = {p: 0 for p in spn.places}
    for t in spn.transitions:
        k = _count_in_service(t)
        if k > 0 and hasattr(t, "input_arcs") and t.input_arcs:
            # Minimal assumption: parallel_timing uses exactly 1 input arc in your implementation
            p_in = t.input_arcs[0].from_place
            reserved_for_place[p_in] = reserved_for_place.get(p_in, 0) + k

    # --- draw places and marking ---
    for place in spn.places:
        waiting = len(place.tokens)
        in_service = reserved_for_place.get(place, 0)
        token_count = waiting + in_service  # displayed total (waiting + hidden/in-service)

        # Label formatting:
        # - if no in-service: keep old behavior (dots for small counts, numeric for >=5)
        # - if in-service exists: show "waiting+in_service" so you can see hidden tokens
        if token_count == 0:
            if print_place_labels:
                spn_graph.node(place.label, shape="circle", label="", xlabel=place.label,
                               height="0.6", width="0.6", fixedsize='true')
            else:
                spn_graph.node(place.label, shape="circle", label="",
                               height="0.6", width="0.6", fixedsize='true')
        else:
            if in_service > 0:
                lb = f"{waiting + in_service}"
            else:
                if token_count < 5:
                    lb = "<"
                    for token_number in range(1, token_count + 1):
                        lb += "&#9679;"
                        if token_number % 2 == 0:
                            lb += "<br/>"
                    lb += ">"
                else:
                    lb = f"{token_count}"

            if print_place_labels:
                xlabel = place.label
                if in_service > 0:
                    xlabel += f"\n(in service: {in_service})"
                spn_graph.node(place.label, shape='circle', label=lb, xlabel=xlabel,
                               height='0.6', width='0.6', fixedsize='true')
            else:
                spn_graph.node(place.label, shape='circle', label=lb,
                               height='0.6', width='0.6', fixedsize='true')

    # --- draw transitions + arcs ---
    for transition in spn.transitions:
        # NEW: show number of active parallel instances on the transition label
        pt_k = _count_in_service(transition)
        extra = f"\nPT:{pt_k}" if getattr(transition, "parallel_timing", False) else ""

        if transition.t_type == "T":
            dist_name = str(list(transition.distribution.keys())[0]) if transition.distribution else ""
            xlabel = transition.label + "\n" + dist_name + extra
            if rankdir == "TB":
                spn_graph.node(transition.label, shape='rectangle', color='black', label='',
                               xlabel=xlabel, height='0.2', width='0.6', fixedsize='true')
            else:
                spn_graph.node(transition.label, shape='rectangle', color='black', label='',
                               xlabel=xlabel, height='0.6', width='0.2', fixedsize='true')
        else:
            xlabel = transition.label + "\n" + str(transition.weight) + extra
            if rankdir == "TB":
                spn_graph.node(transition.label, shape='rectangle', style='filled', color='black', label='',
                               xlabel=xlabel, height='0.2', width='0.6', fixedsize='true')
            else:
                spn_graph.node(transition.label, shape='rectangle', style='filled', color='black', label='',
                               xlabel=xlabel, height='0.6', width='0.2', fixedsize='true')

        for input_arc in transition.input_arcs:
            if input_arc.multiplicity > 1:
                spn_graph.edge(input_arc.from_place.label, input_arc.to_transition.label,
                               xlabel=str(input_arc.multiplicity))
            else:
                spn_graph.edge(input_arc.from_place.label, input_arc.to_transition.label)

        for output_arc in transition.output_arcs:
            if output_arc.multiplicity > 1:
                spn_graph.edge(output_arc.from_transition.label, output_arc.to_place.label,
                               xlabel=str(output_arc.multiplicity))
            else:
                spn_graph.edge(output_arc.from_transition.label, output_arc.to_place.label)

        for inhibitor_arc in transition.inhibitor_arcs:
            if inhibitor_arc.multiplicity > 1:
                spn_graph.edge(inhibitor_arc.from_place.label, inhibitor_arc.to_transition.label,
                               xlabel=str(inhibitor_arc.multiplicity), arrowhead="odot", color="black")
            else:
                spn_graph.edge(inhibitor_arc.from_place.label, inhibitor_arc.to_transition.label,
                               arrowhead="odot", color="black")

    spn_graph.render('../output/graphs/{}.gv'.format(file), view=show)
    return spn_graph