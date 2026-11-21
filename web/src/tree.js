// Use parent links from the API rather than inferring paths from node-id punctuation.
export function pathToNode(nodes, nodeId) {
  const path = [];
  const seen = new Set();
  let node = nodes.find(item => item.node_id === nodeId);
  if (!node) throw new Error('This branch is no longer visible. Please try again.');
  while (node.parent_id !== null) {
    if (seen.has(node.node_id)) throw new Error('The tree contains a circular path.');
    seen.add(node.node_id);
    path.unshift(node.node_id);
    node = nodes.find(item => item.node_id === node.parent_id);
    if (!node) throw new Error('The tree is missing a parent branch.');
  }
  return path;
}

export function validateTree(data) {
  if (!data || !Array.isArray(data.nodes) || !Array.isArray(data.path)
    || !data.nodes.some(node => node.node_id === data.current)) {
    throw new Error('The API returned an incomplete tree. Please retry.');
  }
  const ids = new Set();
  for (const node of data.nodes) {
    // "pruned" = a branch not taken earlier: label only, no result (contract v1.1)
    const pruned = node.status === 'pruned' && node.node_id !== data.current;
    if (typeof node.node_id !== 'string' || ids.has(node.node_id)
      || typeof node.label !== 'string' || !['chosen', 'sibling', 'child', ...(pruned ? ['pruned'] : [])].includes(node.status)
      || (!pruned && (!Number.isFinite(finalNetWorth(node.result)) || !Number.isFinite(node.result?.metrics?.min_cash)))) {
      throw new Error('The API returned invalid branch data. Please retry.');
    }
    ids.add(node.node_id);
  }
  for (const node of data.nodes) pathToNode(data.nodes, node.node_id);
  return data;
}

// Deterministic first (#21: Monte Carlo is opt-in, so p50 may be null), median as a fallback.
export function finalNetWorth(result) {
  const m = result?.metrics || {};
  return [result?.deterministic?.final_net_worth, m.final_net_worth, m.final_net_worth_p50].find(Number.isFinite);
}
