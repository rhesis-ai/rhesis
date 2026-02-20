# Research Assistant Multi-Agent Architecture

## Agent Overview

```mermaid
flowchart TB
    subgraph User["User"]
        Query[User Query]
    end

    subgraph Orchestrator["ORCHESTRATOR"]
        O[Route & Coordinate]
    end

    subgraph Specialists["Specialist Agents"]
        subgraph Safety["SAFETY SPECIALIST"]
            S_Tools["Tools:<br/>• retrieve_safety_data<br/>• retrieve_experimental_data<br/>• analyze_and_score<br/>• identify_gaps<br/>• extract_insights"]
        end
        
        subgraph Target["TARGET SPECIALIST"]
            T_Tools["Tools:<br/>• retrieve_target_info<br/>• retrieve_experimental_data<br/>• analyze_and_score<br/>• compare_entities<br/>• identify_gaps<br/>• filter_and_rank<br/>• extract_insights"]
        end
        
        subgraph Compound["COMPOUND SPECIALIST"]
            C_Tools["Tools:<br/>• retrieve_compound_data<br/>• retrieve_experimental_data<br/>• analyze_and_score<br/>• compare_entities<br/>• compute_routes<br/>• filter_and_rank<br/>• extract_insights"]
        end
        
        subgraph Literature["LITERATURE SPECIALIST"]
            L_Tools["Tools:<br/>• retrieve_literature<br/>• retrieve_patent_data<br/>• extract_insights<br/>• identify_gaps"]
        end
        
        subgraph Market["MARKET SPECIALIST"]
            M_Tools["Tools:<br/>• retrieve_market_data<br/>• retrieve_patent_data<br/>• analyze_and_score<br/>• compare_entities<br/>• extract_insights"]
        end
    end

    subgraph Synthesis["SYNTHESIS AGENT"]
        Syn_Tools["Tools:<br/>• synthesize_report<br/>• generate_recommendations<br/>• format_output<br/>• extract_insights"]
    end

    Query --> O
    O -->|"transfer_to_safety_specialist"| Safety
    O -->|"transfer_to_target_specialist"| Target
    O -->|"transfer_to_compound_specialist"| Compound
    O -->|"transfer_to_literature_specialist"| Literature
    O -->|"transfer_to_market_specialist"| Market
    O -->|"transfer_to_synthesis_agent"| Synthesis

    Safety -->|"transfer_to_synthesis_agent"| Synthesis
    Target -->|"transfer_to_synthesis_agent"| Synthesis
    Compound -->|"transfer_to_synthesis_agent"| Synthesis
    Literature -->|"transfer_to_synthesis_agent"| Synthesis
    Market -->|"transfer_to_synthesis_agent"| Synthesis

    Synthesis -->|Response| Query
```

## Agent Handoff Network

```mermaid
flowchart LR
    subgraph Core["Core Flow"]
        O((Orchestrator))
        SYN((Synthesis))
    end

    subgraph Domain["Domain Specialists"]
        SAF((Safety))
        TGT((Target))
        CMP((Compound))
        LIT((Literature))
        MKT((Market))
    end

    %% Orchestrator routes to all specialists
    O ==>|routes| SAF
    O ==>|routes| TGT
    O ==>|routes| CMP
    O ==>|routes| LIT
    O ==>|routes| MKT
    O ==>|routes| SYN

    %% Cross-specialist handoffs
    SAF <-.->|handoff| TGT
    SAF <-.->|handoff| CMP
    TGT <-.->|handoff| CMP
    TGT <-.->|handoff| LIT
    LIT <-.->|handoff| MKT

    %% All specialists can go to synthesis
    SAF -->|synthesize| SYN
    TGT -->|synthesize| SYN
    CMP -->|synthesize| SYN
    LIT -->|synthesize| SYN
    MKT -->|synthesize| SYN

    %% Synthesis can request more data
    SYN -.->|request data| SAF
    SYN -.->|request data| TGT
    SYN -.->|request data| CMP
```

## Tool Layer Architecture

```mermaid
flowchart TB
    subgraph Layer1["Layer 1: RETRIEVAL"]
        R1[retrieve_safety_data]
        R2[retrieve_literature]
        R3[retrieve_target_info]
        R4[retrieve_compound_data]
        R5[retrieve_market_data]
        R6[retrieve_patent_data]
        R7[retrieve_experimental_data]
    end

    subgraph Layer2["Layer 2: ANALYSIS"]
        A1[analyze_and_score]
        A2[compare_entities]
        A3[identify_gaps]
        A4[filter_and_rank]
        A5[compute_routes]
        A6[extract_insights]
    end

    subgraph Layer3["Layer 3: SYNTHESIS"]
        S1[synthesize_report]
        S2[generate_recommendations]
        S3[format_output]
    end

    Layer1 --> Layer2
    Layer2 --> Layer3

    style Layer1 fill:#e1f5fe
    style Layer2 fill:#fff3e0
    style Layer3 fill:#e8f5e9
```

## Example Workflow: Target Safety Assessment

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant T as Target Specialist
    participant S as Safety Specialist
    participant SYN as Synthesis Agent

    U->>O: "Assess safety of EGFR as a drug target"
    O->>O: Analyze query
    O->>T: transfer_to_target_specialist
    T->>T: retrieve_target_info(EGFR)
    T->>T: analyze_and_score(druggability)
    T->>S: transfer_to_safety_specialist
    S->>S: retrieve_safety_data(EGFR)
    S->>S: analyze_and_score(safety_risk)
    S->>S: identify_gaps()
    S->>SYN: transfer_to_synthesis_agent
    SYN->>SYN: synthesize_report(target_dossier)
    SYN->>SYN: generate_recommendations()
    SYN-->>U: Final Assessment Report
```

## Agent Capabilities Summary

| Agent | Domain Tools | Analysis Tools | Can Transfer To |
|-------|-------------|----------------|-----------------|
| **Orchestrator** | - | - | All Specialists, Synthesis |
| **Safety** | retrieve_safety_data, retrieve_experimental_data | analyze_and_score, identify_gaps, extract_insights | Orchestrator, Target, Compound, Synthesis |
| **Target** | retrieve_target_info, retrieve_experimental_data | analyze_and_score, compare_entities, identify_gaps, filter_and_rank, extract_insights | Orchestrator, Safety, Compound, Literature, Synthesis |
| **Compound** | retrieve_compound_data, retrieve_experimental_data | analyze_and_score, compare_entities, compute_routes, filter_and_rank, extract_insights | Orchestrator, Safety, Target, Synthesis |
| **Literature** | retrieve_literature, retrieve_patent_data | extract_insights, identify_gaps | Orchestrator, Target, Compound, Market, Synthesis |
| **Market** | retrieve_market_data, retrieve_patent_data | analyze_and_score, compare_entities, extract_insights | Orchestrator, Literature, Synthesis |
| **Synthesis** | synthesize_report, generate_recommendations, format_output | extract_insights | Orchestrator, Safety, Target, Compound |
