"use client";

import { useId, useState, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  Handle,
  Position,
  BackgroundVariant,
  Node,
  ViewportPortal,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import type {
  ChatBaselineEntity,
  ChatBaselineRelationship,
  ChatRelationshipStatus,
} from "@/lib/api";

interface CaseRelationshipGraphProps {
  entities: ChatBaselineEntity[];
  relationships: ChatBaselineRelationship[];
}

const STATUS_LABELS: Record<ChatRelationshipStatus, string> = {
  reported: "Reported",
  suspected: "Suspected",
  contradicted: "Contradicted",
  not_established: "Not established",
};

export function CaseRelationshipGraph({
  entities,
  relationships,
}: CaseRelationshipGraphProps) {
  const detailId = useId();
  const [selectedRelationshipId, setSelectedRelationshipId] = useState(
    relationships[0]?.relationship_id ?? "",
  );
  const selectedRelationship =
    relationships.find(
      (relationship) =>
        relationship.relationship_id === selectedRelationshipId,
    ) ?? relationships[0];
  const entitiesById = new Map(
    entities.map((entity) => [entity.entity_id, entity]),
  );

  if (!selectedRelationship) {
    return (
      <section
        aria-label="Candidate entity relationships"
        className="mb-4 min-w-0 max-w-full rounded-xl border border-dashed border-line-strong bg-surface-nested p-4"
      >
        <RelationshipHeader count={0} />
        <RelationshipTrustNotice />
        <p className="mt-3 text-xs leading-5 text-ink-secondary">
          No explicit entity-to-entity relationship was extracted.
        </p>
      </section>
    );
  }

  const selectedSubject = entitiesById.get(
    selectedRelationship.subject_entity_id,
  );
  const selectedObject = entitiesById.get(selectedRelationship.object_entity_id);

  return (
    <section
      aria-label="Candidate entity relationships"
      className="mb-4 min-w-0 max-w-full rounded-xl border border-line bg-surface-nested p-3 sm:p-4"
    >
      <RelationshipHeader count={relationships.length} />
      <RelationshipTrustNotice />

      <div className="mt-5">
        <RelationshipCanvas
          entities={entities}
          relationships={relationships}
          selectedRelationshipId={selectedRelationship.relationship_id}
          onSelectRelationship={setSelectedRelationshipId}
        />
      </div>

      <div className="mt-5 grid min-w-0 max-w-full gap-4 lg:grid-cols-12">
        <div className="min-w-0 lg:col-span-5">
          <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
            Relationship list
          </p>
          <div className="mt-2 space-y-2">
            {relationships.map((relationship) => {
              const subject = entitiesById.get(relationship.subject_entity_id);
              const object = entitiesById.get(relationship.object_entity_id);
              const selected =
                relationship.relationship_id ===
                selectedRelationship.relationship_id;
              return (
                <button
                  key={relationship.relationship_id}
                  type="button"
                  aria-pressed={selected}
                  aria-controls={detailId}
                  onClick={() =>
                    setSelectedRelationshipId(relationship.relationship_id)
                  }
                  className={`w-full rounded-xl border p-3 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-charcoal focus-visible:ring-offset-2 focus-visible:ring-offset-surface-nested ${selected
                      ? "border-charcoal bg-surface shadow-[0_2px_8px_rgba(39,39,39,0.07)]"
                      : "border-line bg-surface hover:border-line-strong hover:bg-surface-hover"
                    }`}
                >
                  <span className="flex items-start justify-between gap-3">
                    <span className="min-w-0 text-sm font-bold leading-5 text-ink [overflow-wrap:anywhere]">
                      {subject?.name ?? relationship.subject_entity_id}
                      <span aria-hidden="true"> → </span>
                      {object?.name ?? relationship.object_entity_id}
                    </span>
                    <span className="shrink-0 text-[9px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                      {relationship.relationship_id}
                    </span>
                  </span>
                  <span className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-ink-secondary">
                    <span className="font-mono [overflow-wrap:anywhere]">
                      {relationship.predicate}
                    </span>
                    <span className="inline-flex items-center gap-1.5 font-bold">
                      <StatusConnector status={relationship.status} />
                      {STATUS_LABELS[relationship.status]}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="min-w-0 max-w-full lg:col-span-7">
          <div
            id={detailId}
            aria-live="polite"
            className="rounded-xl border border-line bg-surface p-4"
          >
            <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
              Selected relationship detail
            </p>
            <p className="mt-2 text-sm font-bold leading-6 text-ink [overflow-wrap:anywhere]">
              {selectedRelationship.statement}
            </p>
            <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-2">
              <div className="sm:col-span-2">
                <dt className="font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                  Source → target
                </dt>
                <dd className="mt-1 leading-5 text-ink [overflow-wrap:anywhere]">
                  {selectedSubject?.name ??
                    selectedRelationship.subject_entity_id}
                  <span aria-hidden="true"> → </span>
                  {selectedObject?.name ?? selectedRelationship.object_entity_id}
                </dd>
              </div>
              <div>
                <dt className="font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                  Status
                </dt>
                <dd className="mt-1 inline-flex items-center gap-1.5 font-bold text-ink">
                  <StatusConnector status={selectedRelationship.status} />
                  {STATUS_LABELS[selectedRelationship.status]}
                </dd>
              </div>
              <div>
                <dt className="font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                  Confidence
                </dt>
                <dd className="mt-1 capitalize text-ink">
                  {selectedRelationship.confidence}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                  Predicate
                </dt>
                <dd className="mt-1 font-mono text-ink [overflow-wrap:anywhere]">
                  {selectedRelationship.predicate}
                </dd>
              </div>
              <div className="sm:col-span-2">
                <dt className="font-extrabold uppercase tracking-[0.1em] text-ink-secondary">
                  Source message IDs
                </dt>
                <dd className="mt-1 flex flex-wrap gap-1.5">
                  {selectedRelationship.source_message_ids.map((messageId) => (
                    <span
                      key={messageId}
                      className="max-w-full rounded border border-line bg-surface-nested px-1.5 py-1 font-mono text-[10px] leading-4 text-ink-secondary [overflow-wrap:anywhere]"
                    >
                      {messageId}
                    </span>
                  ))}
                </dd>
              </div>
            </dl>
          </div>
        </div>
      </div>
    </section>
  );
}

function RelationshipHeader({ count }: { count: number }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
          Dedicated relationship inspector
        </p>
        <h4 className="mt-1 text-sm font-extrabold text-ink">
          Candidate entity relationships
        </h4>
      </div>
      <span className="text-xs font-bold text-ink-secondary">{count}</span>
    </div>
  );
}

function CustomGraphNode({
  data,
}: {
  data: { entityId: string; label: string; selected: boolean };
}) {
  const lines = graphLabelLines(data.label);
  return (
    <div
      data-graph-node-id={data.entityId}
      data-selected={data.selected}
      className={`relative min-w-[172px] max-w-[200px] rounded-xl border p-3 text-center transition-all ${data.selected
          ? "border-charcoal bg-surface-nested ring-2 ring-charcoal shadow-md"
          : "border-line-strong bg-surface hover:border-charcoal hover:bg-surface-hover"
        }`}
    >
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
      <Handle type="target" position={Position.Left} id="left" className="!opacity-0" />
      <Handle type="source" position={Position.Right} id="right" className="!opacity-0" />

      <div className="flex h-full flex-col justify-center gap-1">
        <div className="text-xs font-bold leading-snug text-ink">
          {lines.map((line, idx) => (
            <div key={`${line}-${idx}`}>{line}</div>
          ))}
        </div>
        <div className="font-mono text-[9px] font-semibold text-ink-secondary">
          {clampGraphLabel(data.entityId, 24)}
        </div>
      </div>
    </div>
  );
}

const nodeTypes = { customNode: CustomGraphNode };

function RelationshipCanvas({
  entities,
  relationships,
  selectedRelationshipId,
  onSelectRelationship,
}: {
  entities: ChatBaselineEntity[];
  relationships: ChatBaselineRelationship[];
  selectedRelationshipId: string;
  onSelectRelationship: (id: string) => void;
}) {
  const markerId = `relationship-arrow-${useId().replace(/:/g, "")}`;
  const entitiesById = useMemo(
    () => new Map(entities.map((entity) => [entity.entity_id, entity])),
    [entities],
  );

  const connectedEntityIds = useMemo(
    () =>
      Array.from(
        new Set(
          relationships.flatMap((relationship) => [
            relationship.subject_entity_id,
            relationship.object_entity_id,
          ]),
        ),
      ).sort(),
    [relationships],
  );

  const positionsById = useMemo(
    () => computeLayeredNodePositions(entities, relationships),
    [entities, relationships],
  );

  const graphEntities = useMemo(
    () =>
      connectedEntityIds.map((entityId, index) => ({
        entityId,
        entity: entitiesById.get(entityId),
        position:
          positionsById.get(entityId) || graphNodePosition(index),
      })),
    [connectedEntityIds, entitiesById, positionsById],
  );

  const selectedRelationship = useMemo(
    () =>
      relationships.find(
        (rel) => rel.relationship_id === selectedRelationshipId,
      ),
    [relationships, selectedRelationshipId],
  );

  const selectedEndpointIds = useMemo(
    () =>
      new Set(
        selectedRelationship
          ? [
            selectedRelationship.subject_entity_id,
            selectedRelationship.object_entity_id,
          ]
          : [],
      ),
    [selectedRelationship],
  );

  const pairGroups = useMemo(() => {
    const map = new Map<string, ChatBaselineRelationship[]>();
    for (const rel of relationships) {
      const pairKey = [rel.subject_entity_id, rel.object_entity_id]
        .sort()
        .join("::");
      const group = map.get(pairKey) || [];
      group.push(rel);
      map.set(pairKey, group);
    }
    return map;
  }, [relationships]);

  const sortedRelationships = useMemo(() => {
    return [...relationships].sort((a, b) => {
      if (a.relationship_id === selectedRelationshipId) return 1;
      if (b.relationship_id === selectedRelationshipId) return -1;
      return 0;
    });
  }, [relationships, selectedRelationshipId]);

  const initialNodes: Node[] = useMemo(() => {
    return graphEntities.map(({ entityId, entity, position }) => ({
      id: entityId,
      type: "customNode",
      position: { x: position.left, y: position.top },
      data: {
        entityId,
        label: entity?.name ?? entityId,
        selected: false,
      },
    }));
  }, [graphEntities]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);

  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setNodes((prevNodes) =>
      prevNodes.map((node) => {
        const isSelected = selectedEndpointIds.has(node.id);
        if (node.data.selected === isSelected) return node;
        return {
          ...node,
          data: {
            ...node.data,
            selected: isSelected,
          },
        };
      })
    );
  }, [selectedEndpointIds, setNodes]);

  return (
    <div className="min-w-0 max-w-full rounded-xl border border-line bg-surface p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-extrabold uppercase tracking-[0.14em] text-ink-secondary">
          Relationship canvas
        </p>
        <p className="text-[10px] text-ink-secondary">
          Drag nodes to reposition · Zoom & Pan enabled
        </p>
      </div>
      <div
        data-relationship-graph-scroller="true"
        className="mt-2 h-[420px] min-w-0 max-w-full overflow-x-auto rounded-lg border border-line bg-surface overflow-hidden"
      >
        <ReactFlow
          nodes={nodes}
          onNodesChange={onNodesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.4}
          maxZoom={2}
          proOptions={{ hideAttribution: true }}
        >
          <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="var(--color-line)" />
          <Controls className="!rounded-lg !border-line !bg-surface !shadow-sm" />

          <ViewportPortal>
            <svg
              aria-hidden="true"
              data-relationship-graph="true"
              className="react-flow__edges h-[420px] min-w-[960px]"
              style={{ overflow: "visible", pointerEvents: "none" }}
            >
              <defs>
                <marker
                  id={markerId}
                  markerWidth="8"
                  markerHeight="8"
                  refX="7"
                  refY="4"
                  orient="auto"
                  markerUnits="strokeWidth"
                >
                  <path d="M0,0 L8,4 L0,8 Z" fill="var(--color-charcoal)" />
                </marker>
              </defs>

              {sortedRelationships.map((relationship) => {
                const sourceNode = nodes.find(
                  (n) => n.id === relationship.subject_entity_id,
                );
                const targetNode = nodes.find(
                  (n) => n.id === relationship.object_entity_id,
                );
                const sourcePos = sourceNode
                  ? {
                    left: sourceNode.position.x,
                    top: sourceNode.position.y,
                    x: sourceNode.position.x + GRAPH_NODE_WIDTH / 2,
                    y: sourceNode.position.y + GRAPH_NODE_HEIGHT / 2,
                  }
                  : positionsById.get(relationship.subject_entity_id);
                const targetPos = targetNode
                  ? {
                    left: targetNode.position.x,
                    top: targetNode.position.y,
                    x: targetNode.position.x + GRAPH_NODE_WIDTH / 2,
                    y: targetNode.position.y + GRAPH_NODE_HEIGHT / 2,
                  }
                  : positionsById.get(relationship.object_entity_id);

                if (!sourcePos || !targetPos) return null;

                const pairKey = [
                  relationship.subject_entity_id,
                  relationship.object_entity_id,
                ]
                  .sort()
                  .join("::");
                const group = pairGroups.get(pairKey) || [relationship];
                const indexInPair = group.findIndex(
                  (r) => r.relationship_id === relationship.relationship_id,
                );

                return (
                  <GraphEdge
                    key={relationship.relationship_id}
                    relationship={relationship}
                    source={sourcePos}
                    target={targetPos}
                    markerId={markerId}
                    selected={
                      relationship.relationship_id === selectedRelationshipId
                    }
                    indexInPair={indexInPair}
                    totalInPair={group.length}
                    onSelect={() => onSelectRelationship(relationship.relationship_id)}
                  />
                );
              })}
            </svg>
          </ViewportPortal>
        </ReactFlow>
      </div>

      <GraphLegend />
    </div>
  );
}

const GRAPH_NODE_WIDTH = 172;
const GRAPH_NODE_HEIGHT = 78;

interface GraphPoint {
  x: number;
  y: number;
}

interface GraphNodePosition extends GraphPoint {
  left: number;
  top: number;
}

function GraphEdge({
  relationship,
  source,
  target,
  markerId,
  selected,
  indexInPair,
  totalInPair,
  onSelect,
}: {
  relationship: ChatBaselineRelationship;
  source: GraphNodePosition;
  target: GraphNodePosition;
  markerId: string;
  selected: boolean;
  indexInPair: number;
  totalInPair: number;
  onSelect: () => void;
}) {
  const isSelf =
    relationship.subject_entity_id === relationship.object_entity_id;
  const strokeWidth = selected ? 3 : 1.5;
  const opacity = selected ? 1 : 0.65;

  let pathD = "";
  let labelX = 0;
  let labelY = 0;
  let midX = 0;
  let midY = 0;

  if (isSelf) {
    const rightEdge = source.left + GRAPH_NODE_WIDTH;
    const startY = source.top + 20;
    const endY = source.top + GRAPH_NODE_HEIGHT - 20;
    const controlX = rightEdge + 50;
    const controlY = source.y;

    pathD = `M ${rightEdge} ${startY} Q ${controlX} ${controlY} ${rightEdge} ${endY}`;
    labelX = rightEdge + 35;
    labelY = source.y;
    midX = labelX;
    midY = labelY;
  } else {
    const dx = target.x - source.x;
    const dy = target.y - source.y;
    const dist = Math.hypot(dx, dy) || 1;
    const ux = dx / dist;
    const uy = dy / dist;
    const nx = -uy;
    const ny = ux;

    let offset = (indexInPair - (totalInPair - 1) / 2) * 36;
    if (totalInPair === 1) {
      if (Math.abs(dy) < 30) {
        offset = Math.abs(dx) > 300 ? -65 : -24;
      } else if (Math.abs(dx) > 10 && Math.abs(dy) > 10) {
        const sign =
          source.left < target.left && source.top < target.top ? 1 : -1;
        offset = sign * 24;
      }
    }

    const rawMidX = (source.x + target.x) / 2;
    const rawMidY = (source.y + target.y) / 2;
    const controlX = rawMidX + nx * offset;
    const controlY = rawMidY + ny * offset;

    const startScale = rectangleBoundaryScale(
      controlX - source.x,
      controlY - source.y,
    );
    const startX = source.x + (controlX - source.x) * startScale;
    const startY = source.y + (controlY - source.y) * startScale;

    const endScale = rectangleBoundaryScale(
      controlX - target.x,
      controlY - target.y,
    );
    const endX = target.x + (controlX - target.x) * endScale;
    const endY = target.y + (controlY - target.y) * endScale;

    pathD = `M ${startX} ${startY} Q ${controlX} ${controlY} ${endX} ${endY}`;
    labelX = 0.25 * startX + 0.5 * controlX + 0.25 * endX;
    labelY = 0.25 * startY + 0.5 * controlY + 0.25 * endY;
    midX = labelX;
    midY = labelY;
  }

  const labelText = clampGraphLabel(relationship.predicate, 28);
  const badgeWidth = Math.max(54, labelText.length * 6.2 + 14);
  const badgeHeight = 18;

  return (
    <g
      data-graph-edge-id={relationship.relationship_id}
      data-selected={selected}
      opacity={opacity}
      className="pointer-events-auto cursor-pointer"
      onClick={onSelect}
    >
      <path
        d={pathD}
        fill="none"
        stroke="var(--color-charcoal)"
        strokeWidth={strokeWidth}
        strokeDasharray={connectorDashArray(relationship.status)}
        markerEnd={`url(#${markerId})`}
      />
      {relationship.status === "contradicted" && (
        <g stroke="var(--color-charcoal)" strokeWidth={selected ? 3 : 2}>
          <line
            x1={midX - badgeWidth / 2 - 10}
            y1={midY - 5}
            x2={midX - badgeWidth / 2 - 2}
            y2={midY + 5}
          />
          <line
            x1={midX - badgeWidth / 2 - 2}
            y1={midY - 5}
            x2={midX - badgeWidth / 2 - 10}
            y2={midY + 5}
          />
        </g>
      )}
      <g transform={`translate(${labelX}, ${labelY})`}>
        <rect
          x={-badgeWidth / 2}
          y={-badgeHeight / 2}
          width={badgeWidth}
          height={badgeHeight}
          rx="9"
          fill="var(--color-ivory)"
          stroke={selected ? "var(--color-charcoal)" : "var(--color-line-strong)"}
          strokeWidth={selected ? 2 : 1}
        />
        <text
          data-graph-edge-label={relationship.relationship_id}
          x={0}
          y={3.5}
          textAnchor="middle"
          fill="var(--color-charcoal)"
          fontFamily="ui-monospace, SFMono-Regular, Menlo, monospace"
          fontSize={selected ? 10 : 9}
          fontWeight={selected ? 800 : 600}
        >
          {labelText}
        </text>
      </g>
    </g>
  );
}

function computeLayeredNodePositions(
  entities: ChatBaselineEntity[],
  relationships: ChatBaselineRelationship[],
): Map<string, GraphNodePosition> {
  const connectedIds = Array.from(
    new Set(
      relationships.flatMap((r) => [r.subject_entity_id, r.object_entity_id]),
    ),
  );

  const allEntityIds = Array.from(
    new Set([
      ...connectedIds,
      ...entities.map((e) => e.entity_id),
    ]),
  );

  if (allEntityIds.length === 0) return new Map();

  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, Set<string>>();
  allEntityIds.forEach((id) => {
    inDegree.set(id, 0);
    outEdges.set(id, new Set());
  });

  for (const rel of relationships) {
    if (rel.subject_entity_id !== rel.object_entity_id) {
      outEdges.get(rel.subject_entity_id)?.add(rel.object_entity_id);
      inDegree.set(
        rel.object_entity_id,
        (inDegree.get(rel.object_entity_id) || 0) + 1,
      );
    }
  }

  const layers = new Map<string, number>();
  const queue: { id: string; layer: number }[] = [];

  allEntityIds.forEach((id) => {
    if ((inDegree.get(id) || 0) === 0) {
      queue.push({ id, layer: 0 });
      layers.set(id, 0);
    }
  });

  if (queue.length === 0 && allEntityIds.length > 0) {
    queue.push({ id: allEntityIds[0], layer: 0 });
    layers.set(allEntityIds[0], 0);
  }

  const visited = new Set<string>();
  while (queue.length > 0) {
    const { id, layer } = queue.shift()!;
    if (visited.has(id)) continue;
    visited.add(id);

    const currentLayer = layers.get(id) ?? layer;
    const targets = outEdges.get(id) || new Set();
    for (const targetId of targets) {
      const nextLayer = Math.max(layers.get(targetId) ?? 0, currentLayer + 1);
      layers.set(targetId, nextLayer);
      queue.push({ id: targetId, layer: nextLayer });
    }
  }

  allEntityIds.forEach((id) => {
    if (!layers.has(id)) layers.set(id, 0);
  });

  const nodesByLayer = new Map<number, string[]>();
  allEntityIds.forEach((id) => {
    const l = layers.get(id) || 0;
    const list = nodesByLayer.get(l) || [];
    list.push(id);
    nodesByLayer.set(l, list);
  });

  const posMap = new Map<string, GraphNodePosition>();
  const sortedLayerKeys = Array.from(nodesByLayer.keys()).sort((a, b) => a - b);

  sortedLayerKeys.forEach((layerIndex, colIdx) => {
    const nodeIdsInLayer = nodesByLayer.get(layerIndex) || [];
    nodeIdsInLayer.forEach((id, rowIdx) => {
      const left = 48 + colIdx * 360;
      const stagger = colIdx % 2 === 1 ? 36 : 0;
      const top = 40 + rowIdx * 220 + stagger;
      posMap.set(id, {
        left,
        top,
        x: left + GRAPH_NODE_WIDTH / 2,
        y: top + GRAPH_NODE_HEIGHT / 2,
      });
    });
  });

  return posMap;
}

function graphNodePosition(index: number): GraphNodePosition {
  const column = Math.floor(index / 2);
  const row = index % 2;
  const left = 48 + column * 360;
  const top = row === 0 ? 40 : 250;
  return {
    left,
    top,
    x: left + GRAPH_NODE_WIDTH / 2,
    y: top + GRAPH_NODE_HEIGHT / 2,
  };
}

function rectangleBoundaryScale(deltaX: number, deltaY: number): number {
  if (deltaX === 0 && deltaY === 0) return 0;
  const horizontalScale =
    deltaX === 0 ? Number.POSITIVE_INFINITY : GRAPH_NODE_WIDTH / 2 / Math.abs(deltaX);
  const verticalScale =
    deltaY === 0 ? Number.POSITIVE_INFINITY : GRAPH_NODE_HEIGHT / 2 / Math.abs(deltaY);
  const scale = Math.min(horizontalScale, verticalScale);
  return Number.isFinite(scale) ? scale : 0;
}

function GraphLegend() {
  const statuses: ChatRelationshipStatus[] = [
    "reported",
    "suspected",
    "contradicted",
    "not_established",
  ];
  return (
    <div
      data-graph-legend="true"
      className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 px-1 text-xs text-ink-secondary"
    >
      {statuses.map((status) => (
        <div key={status} className="flex items-center gap-2">
          <StatusConnector status={status} />
          <span className="font-bold text-ink">
            {STATUS_LABELS[status]}
          </span>
        </div>
      ))}
    </div>
  );
}

function StatusConnector({ status }: { status: ChatRelationshipStatus }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 38 14" className="h-3.5 w-9">
      {status === "not_established" ? (
        <>
          <line
            x1="1"
            y1="7"
            x2="14"
            y2="7"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="2 5"
          />
          <line
            x1="24"
            y1="7"
            x2="37"
            y2="7"
            stroke="currentColor"
            strokeWidth="2"
            strokeDasharray="2 5"
          />
        </>
      ) : (
        <line
          x1="1"
          y1="7"
          x2="37"
          y2="7"
          stroke="currentColor"
          strokeWidth="2"
          strokeDasharray={connectorDashArray(status)}
        />
      )}
      {status === "contradicted" && (
        <g stroke="currentColor" strokeWidth="2">
          <line x1="15" y1="2" x2="23" y2="12" />
          <line x1="23" y1="2" x2="15" y2="12" />
        </g>
      )}
    </svg>
  );
}

function RelationshipLabels() {
  return (
    <div className="mt-3 flex flex-wrap gap-1.5" aria-label="Relationship labels">
      {[
        "Candidate",
        "User-reported",
        "Unverified",
      ].map((label) => (
        <span
          key={label}
          className="rounded-full border border-line-strong bg-surface-nested px-2 py-0.5 text-[9px] font-extrabold uppercase tracking-[0.1em] text-ink-secondary"
        >
          {label}
        </span>
      ))}
    </div>
  );
}

function RelationshipTrustNotice() {
  return (
    <>
      <RelationshipLabels />
      <p className="mt-2 text-xs leading-5 text-ink-secondary">
        These source-explicit relationships are candidate, user-reported, and
        unverified. The graph is a visual inspection aid, not forensic proof.
      </p>
    </>
  );
}

function connectorDashArray(status: ChatRelationshipStatus) {
  if (status === "suspected") return "10 7";
  if (status === "not_established") return "2 8";
  return undefined;
}

function graphLabelLines(value: string): string[] {
  const normalized = value.trim();
  if (normalized.length <= 25) return [normalized];
  const firstBreak = normalized.lastIndexOf(" ", 25);
  const splitAt = firstBreak > 10 ? firstBreak : 25;
  return [
    normalized.slice(0, splitAt).trim(),
    clampGraphLabel(normalized.slice(splitAt).trim(), 25),
  ];
}

function clampGraphLabel(value: string, maxLength: number): string {
  return value.length <= maxLength
    ? value
    : `${value.slice(0, Math.max(1, maxLength - 1))}…`;
}
