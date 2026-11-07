def adjacency(topology, count=5):
    if count != 5:
        raise ValueError("Protocol 1.0 requires five agents")
    return study_adjacency(topology, count)


def study_adjacency(topology, count=5):
    if not isinstance(count, int) or isinstance(count, bool) or not 5 <= count <= 128:
        raise ValueError("Study agent count must be 5..128")
    graph = {f"agent_{i}": set() for i in range(count)}
    if topology == "ring":
        edges = [(i, (i + 1) % count) for i in range(count)]
    elif topology == "star":
        edges = [(0, i) for i in range(1, count)]
    elif topology == "complete":
        edges = [(i, j) for i in range(count) for j in range(i + 1, count)]
    else:
        raise ValueError("Unknown topology")
    for a, b in edges:
        graph[f"agent_{a}"].add(f"agent_{b}")
        graph[f"agent_{b}"].add(f"agent_{a}")
    return {key: sorted(value) for key, value in graph.items()}


def distance(graph, source, target):
    frontier, seen = [(source, 0)], {source}
    for node, depth in frontier:
        if node == target:
            return depth
        for neighbor in graph[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                frontier.append((neighbor, depth + 1))
    return None
