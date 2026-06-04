# MITRE ATT&CK Database Schema Design for RAG

To build an advanced Retrieval-Augmented Generation (RAG) system using the MITRE ATT&CK dataset, a hybrid database approach combining a **Graph Database** (e.g., Neo4j) and a **Vector Database** (e.g., Milvus, Qdrant, ChromaDB, or Pinecone) is highly recommended. 

The MITRE ATT&CK dataset (structured in STIX 2.1 format) inherently represents a highly interconnected knowledge graph (Entities and Relationships). 
* The **Graph DB** will store the structured relationships, allowing for complex multi-hop queries (e.g., "What mitigations exist for the techniques used by the software that APT29 uses?").
* The **Vector DB** will store dense vector embeddings of the unstructured text (descriptions), allowing for semantic search (e.g., "How do threat actors steal browser cookies?").

---

## 1. Graph Database Schema (Property Graph Model)

The Graph Database captures the exact structure of the STIX 2.1 data.

### **Nodes (Entities)**

| Node Label | STIX 2.1 Type | Key Properties | Description |
| :--- | :--- | :--- | :--- |
| **`Technique`** | `attack-pattern` | `stix_id`, `attack_id` (e.g., T1566), `name`, `description`, `platforms`, `url` | Core actions performed by adversaries. |
| **`Subtechnique`** | `attack-pattern` | `stix_id`, `attack_id` (e.g., T1566.001), `name`, `description`, `platforms`, `url` | More specific implementations of a Technique. |
| **`Group`** | `intrusion-set` | `stix_id`, `attack_id` (e.g., G0016), `name`, `description`, `aliases` | Adversary groups (e.g., APT29). |
| **`Software`** | `tool` / `malware` | `stix_id`, `attack_id` (e.g., S0154), `name`, `description`, `aliases`, `type` | Tools or malware used by adversaries. |
| **`Campaign`** | `campaign` | `stix_id`, `attack_id` (e.g., C0015), `name`, `description`, `aliases` | Specific threat actor campaigns. |
| **`Mitigation`** | `course-of-action` | `stix_id`, `attack_id` (e.g., M1036), `name`, `description` | Defensive actions to prevent techniques. |
| **`Tactic`** | `x-mitre-tactic` | `stix_id`, `attack_id` (e.g., TA0001), `name`, `shortname`, `description` | Adversary's technical goals (e.g., Initial Access). |
| **`DataSource`** | `x-mitre-data-source`| `stix_id`, `attack_id`, `name`, `description`, `platforms` | Information collected by sensors/logs. |
| **`DataComponent`** | `x-mitre-data-component` | `stix_id`, `name`, `description` | Specific context within a data source. |

### **Edges (Relationships)**

Edges connect the nodes and also contain properties, especially the relationship `description` which details *how* or *why* the relationship exists.

| Edge Label | Source Node | Target Node | Properties |
| :--- | :--- | :--- | :--- |
| **`USES`** | `Group`, `Software`, `Campaign` | `Technique`, `Subtechnique`, `Software` | `stix_id`, `description` (Crucial for RAG context) |
| **`SUBTECHNIQUE_OF`** | `Subtechnique` | `Technique` | `stix_id` |
| **`MITIGATES`** | `Mitigation` | `Technique`, `Subtechnique` | `stix_id`, `description` |
| **`ATTRIBUTED_TO`** | `Campaign` | `Group` | `stix_id`, `description` |
| **`IN_TACTIC`** | `Technique`, `Subtechnique` | `Tactic` | *Derived from `kill_chain_phases`* |
| **`DETECTS`** | `DataComponent` | `Technique`, `Subtechnique` | `stix_id`, `description` |
| **`HAS_COMPONENT`** | `DataSource` | `DataComponent` | `stix_id` |

---

## 2. Vector Database Schema (Qdrant)

The Vector DB enables semantic search over the vast amount of unstructured text within ATT&CK. We use **Qdrant** configured for **Hybrid Search** (Dense + Sparse vectors). To maximize retrieval quality, we embed both **Entities** (nodes) and **Relationships** (edges).

### **Document Structure for Vector DB (Qdrant PointStruct)**

| Field | Type | Description |
| :--- | :--- | :--- |
| **`id`** | `UUID` | Unique identifier generated from the STIX ID (Qdrant requires UUID or integer). |
| **`vector`** | `Dict[str, Vector]` | The hybrid vector representation containing both `"dense"` (e.g., 1024-dim BGE-M3) and `"sparse"` (lexical weights) vectors. |
| **`payload`** | `JSON/Dict` | Metadata payload for filtering and linking to the Graph DB, including the `document` (text content). |

**How Qdrant Stores Sparse Vectors (Named Vectors):**
Unlike older vector databases that only accept a single array per document, Qdrant supports **Named Vectors**. The sparse vector (which contains keyword/lexical weights) is stored directly alongside the dense semantic vector inside the same `vector` field. Because it's structured as a dictionary (`{"dense": [...], "sparse": [...]}`), Qdrant can perform Hybrid Search across both vector types simultaneously during retrieval.

### **Metadata (Payload) Schema**
The payload allows pre-filtering during Vector Search (e.g., "Only search within Groups") and enables linking back to the Graph DB. The actual text embedded is stored inside the payload under `document`.

**Example: Entity Payload**
```json
{
  "stix_id": "intrusion-set--899ce53f-13a0-479b-a0e4-67d46e241542",
  "attack_id": "G0016",
  "entity_type": "Node",
  "node_label": "Group",
  "name": "APT29",
  "domain": "enterprise",
  "url": "https://attack.mitre.org/groups/G0016",
  "document": "Group: APT29. APT29 is threat group that has been attributed to Russia's Foreign Intelligence Service (SVR)..."
}
```

**Example: Relationship Payload**
```json
{
  "stix_id": "relationship--008ef61a-e717-4835-ab3f-a5f1ef1e89ce",
  "entity_type": "Relationship",
  "edge_label": "USES",
  "source_id": "intrusion-set--899ce53f-13a0-479b-a0e4-67d46e241542",
  "target_id": "attack-pattern--01a5a209-b94c-450b-b7f9-946497d91055",
  "source_name": "APT29",
  "target_name": "WMI",
  "document": "APT29 USES WMI: APT29 has used WMI for execution."
}
```

### **What to Embed (Chunking Strategy)**

1. **Entity Descriptions:** Embed the `name` + `description` of every Node (Techniques, Groups, Software, Mitigations).
   * *Example:* "Technique: Phishing. Adversaries may send phishing messages to gain access to victim systems..."
2. **Relationship Descriptions (Crucial):** STIX relationships often contain highly specific text. For instance, the `USES` relationship between APT29 and Phishing might describe *exactly how* APT29 conducts phishing.
   * *Example:* "APT29 has used spearphishing emails with malicious attachments to compromise target networks..."
   * *Embedding format:* "[Source Name] [Relationship Type] [Target Name]: [Relationship Description]"

---

## 3. How they work together in RAG (GraphRAG Architecture)

When a user asks a question (e.g., *"How do adversaries usually establish persistence using scheduled tasks?"*):

1. **Semantic Search (Vector DB):** 
   * Embed the user's query.
   * Query the Vector DB to retrieve the top-K most semantically similar documents (these might be Technique nodes, Mitigation nodes, or Relationship descriptions).
2. **Graph Expansion (Graph DB):**
   * Extract the `stix_id`s from the metadata of the retrieved Vector DB documents.
   * Query the Graph DB using these `stix_id`s to fetch a subgraph. For example, if "Scheduled Task/Job" (T1053) was retrieved, the Graph DB fetches all Groups that *USE* it, all Mitigations that *MITIGATE* it, and its *Subtechniques*.
3. **Context Assembly:**
   * Combine the semantic descriptions from the Vector DB with the structured paths from the Graph DB (e.g., "T1053 is used by APT29 and mitigated by M1047").
4. **LLM Generation:**
   * Feed the assembled context + user query into the LLM to generate a highly accurate, grounded, and comprehensive answer.
