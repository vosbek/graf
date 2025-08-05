# Enhanced Codebase Ingestion - Detailed Implementation & Documentation TODO List
## For Kiro - Documentation & Implementation Support

---

## **📋 EXECUTIVE SUMMARY**

The enhanced ingestion pipeline has been **80% implemented** with core business relationship extraction working. This TODO list covers:
- **IMMEDIATE TESTING** (Priority 1) - Verify working system
- **DOCUMENTATION NEEDS** (Priority 2) - User guides and API docs  
- **REMAINING IMPLEMENTATION** (Priority 3) - Optional enhancements
- **PRODUCTION READINESS** (Priority 4) - Error handling and optimization

---

## **🚨 PRIORITY 1: IMMEDIATE TESTING & VALIDATION**

### **T1.1: Container Restart & Environment Validation**
**Assignee:** Development Team  
**Estimated Time:** 30 minutes  
**Status:** 🔴 CRITICAL - Must be done first

**Tasks:**
- [ ] Restart all Docker containers to pick up embedding model fix (`microsoft/codebert-base`)
- [ ] Verify Neo4j schema creation with new business node types
- [ ] Check ChromaDB connection with correct embedding dimensions (768d)
- [ ] Validate API health endpoints return `ready` status
- [ ] Test basic repository indexing endpoint

**Validation Criteria:**
- All containers start without errors
- Neo4j shows new constraints for `BusinessRule`, `StrutsAction`, `CORBAInterface`, `JSPComponent`
- API `/health/ready` returns business component status

---

### **T1.2: Test Repository Indexing with Legacy Framework Files**
**Assignee:** Development Team  
**Estimated Time:** 1-2 hours  
**Status:** 🔴 CRITICAL

**Preparation:**
- [ ] Create test repository with sample files:
  - Sample JSP with Struts tags (`<html:form>`, `<logic:iterate>`)
  - Sample Java Action class with business logic
  - Sample CORBA IDL interface definition
  - Sample struts-config.xml with action mappings
  - Sample JSP with scriptlets containing validation logic

**Testing Tasks:**
- [ ] Index test repository via API: `POST /api/v1/repositories`
- [ ] Monitor processing logs for business analysis extraction
- [ ] Verify Neo4j database contains business nodes after indexing
- [ ] Check ChromaDB for enhanced chunk metadata
- [ ] Test error handling with malformed legacy files

**Success Criteria:**
- Repository processes without fatal errors
- Neo4j contains `StrutsAction`, `JSPComponent`, `BusinessRule` nodes
- Graph API returns business relationships (not just files)

---

### **T1.3: Dependency Graph Visualization Verification**
**Assignee:** Development Team + Frontend  
**Estimated Time:** 1 hour  
**Status:** 🔴 CRITICAL

**Tasks:**
- [ ] Access dependency graph UI for test repository
- [ ] Verify business nodes appear (not just files and Maven artifacts)
- [ ] Check node tooltips show business context (business_purpose, migration_complexity)
- [ ] Test graph depth controls (depth=2,3,4) show more business relationships
- [ ] Verify node coloring/icons differentiate business components

**Success Criteria:**
- Graph shows Struts actions, CORBA interfaces, JSP components as distinct nodes
- Relationships between business components are visible
- Node metadata includes migration-relevant information

---

### **T1.4: Golden Questions Validation Test**
**Assignee:** Business Analyst + Development Team  
**Estimated Time:** 2 hours  
**Status:** 🔴 CRITICAL

**Test Questions (from provided examples):**
- [ ] **Q1:** "What JSP contains the code that displays Account Information for Universal Life contracts?"
  - Expected: Should find JSP file path and business purpose
- [ ] **Q2:** "Where does the 'Specified Amount' field get its data from?"  
  - Expected: Should trace JSP field → Action → Service → Database
- [ ] **Q3:** "What determines the display value for contract type?"
  - Expected: Should identify business logic in JSP/Action
- [ ] **Q4:** "What Items enable access to documentCenter.action?"
  - Expected: Should find security/access control patterns

**Testing Method:**
- [ ] Use Strands agent chat interface to ask golden questions
- [ ] Document actual responses vs expected business context
- [ ] Verify agent can reference specific file paths and business components
- [ ] Test follow-up questions about migration complexity

---

## **📚 PRIORITY 2: DOCUMENTATION & USER GUIDANCE**

### **T2.1: Enhanced Ingestion Architecture Documentation**
**Assignee:** Kiro + Technical Writer  
**Estimated Time:** 4-6 hours  
**Status:** 🟡 HIGH PRIORITY

**Documentation Needed:**

#### **2.1.A: System Architecture Overview**
- [ ] Create architectural diagram showing enhanced pipeline flow:
  ```
  Source Repository → Tree-sitter Parser → Business Analysis → Neo4j/ChromaDB → Graph API → UI
  ```
- [ ] Document new node types and their relationships
- [ ] Explain business context extraction vs basic file indexing
- [ ] Show integration points with existing components

#### **2.1.B: Business Component Reference**
- [ ] **Struts Components:**
  - Action classes and their business purposes
  - JSP pages with embedded business logic
  - Form validation patterns and migration notes
  - Navigation flows and URL mappings

- [ ] **CORBA Components:**
  - Interface definitions and service contracts
  - Operation signatures and business operations
  - Client-server relationship mapping
  - Migration to GraphQL service patterns

- [ ] **Business Rules:**
  - Validation logic extraction from Java/JSP
  - Business domain classification (security, financial, validation)
  - Complexity scoring for migration planning
  - Rule location and context information

#### **2.1.C: Migration Context Documentation**
- [ ] Migration complexity scoring explanation (low/medium/high)
- [ ] Framework pattern → Modern equivalent mapping
- [ ] Business rule → GraphQL resolver conversion patterns
- [ ] JSP → Angular component migration templates

---

### **T2.2: API Documentation Updates**
**Assignee:** Kiro  
**Estimated Time:** 3-4 hours  
**Status:** 🟡 HIGH PRIORITY

**API Documentation Tasks:**

#### **2.2.A: Graph Visualization API**
- [ ] Update `/api/v1/graph/visualization` documentation
- [ ] Document new node types in response schema:
  ```json
  {
    "type": "struts_action",
    "business_purpose": "customer_account_management", 
    "migration_complexity": "medium"
  }
  ```
- [ ] Document relationship types: `IMPLEMENTS_BUSINESS_RULE`, `CALLS_SERVICE`, etc.
- [ ] Add examples of business-level graph responses

#### **2.2.B: Repository Indexing API**
- [ ] Document enhanced indexing process for legacy frameworks
- [ ] Add examples of processing JSP, CORBA IDL, struts-config.xml files
- [ ] Document business analysis results in API responses
- [ ] Show error handling for unsupported legacy patterns

#### **2.2.C: Query API Enhancements**
- [ ] Document business context in search results
- [ ] Add examples of migration-focused queries
- [ ] Show how to filter by business domain or complexity
- [ ] Document cross-repository business dependency queries

---

### **T2.3: User Guide for Legacy Application Analysis**
**Assignee:** Kiro + Business Analyst  
**Estimated Time:** 6-8 hours  
**Status:** 🟡 HIGH PRIORITY

**User Guide Sections:**

#### **2.3.A: Getting Started with Legacy Analysis**
- [ ] **Prerequisites:** Repository structure requirements
- [ ] **Supported Frameworks:** Struts 1.x/2.x, CORBA IDL, JSP/Servlet
- [ ] **File Type Support:** .jsp, .tag, .java, .xml, .idl
- [ ] **Quick Start:** Index your first legacy repository

#### **2.3.B: Understanding Business Relationships**
- [ ] **Reading the Dependency Graph:** Business vs technical relationships
- [ ] **Node Types Guide:** What each business component represents
- [ ] **Relationship Interpretation:** How components connect
- [ ] **Migration Planning:** Using complexity scores for prioritization

#### **2.3.C: Migration Analysis Workflows**
- [ ] **Struts to Angular Migration:** Step-by-step analysis process
- [ ] **CORBA to GraphQL Migration:** Service contract analysis
- [ ] **JSP to Modern UI Migration:** Component identification
- [ ] **Business Rule Extraction:** Finding and documenting validation logic

#### **2.3.D: Troubleshooting Guide**
- [ ] **Common Issues:** Framework patterns not recognized
- [ ] **Performance:** Large legacy codebase indexing
- [ ] **Accuracy:** When business analysis might be incomplete
- [ ] **Migration Complexity:** Understanding scoring factors

---

### **T2.4: Developer Setup & Configuration Guide**
**Assignee:** Kiro  
**Estimated Time:** 2-3 hours  
**Status:** 🟡 MEDIUM PRIORITY

**Developer Documentation:**
- [ ] **Environment Setup:** Enhanced ingestion pipeline requirements
- [ ] **Configuration Reference:** New embedding model settings
- [ ] **Neo4j Schema:** Business node types and constraints
- [ ] **Tree-sitter Setup:** Language parser configuration
- [ ] **Debug Guide:** Troubleshooting business analysis extraction
- [ ] **Performance Tuning:** Optimization for large legacy codebases

---

## **🔧 PRIORITY 3: REMAINING IMPLEMENTATION**

### **T3.1: ChromaDB Business Context Integration**
**Assignee:** Development Team  
**Estimated Time:** 4-6 hours  
**Status:** 🟡 MEDIUM PRIORITY

**Current Status:** Business analysis extracted but not stored in ChromaDB metadata

**Implementation Tasks:**
- [ ] Enhance chunk metadata with business context:
  ```python
  chunk_metadata = {
      "business_domain": "financial",
      "framework_patterns": ["struts_action", "jsp_scriptlet"],
      "migration_complexity": "high",
      "business_rules": ["amount_validation", "customer_verification"]
  }
  ```
- [ ] Update semantic search to include business context filters
- [ ] Add business-aware similarity scoring
- [ ] Test enhanced embeddings with migration-focused queries

**Success Criteria:**
- ChromaDB chunks contain business metadata
- Semantic search can filter by business domain
- Migration-related queries return more relevant results

---

### **T3.2: Cross-Repository Business Analysis**
**Assignee:** Development Team  
**Estimated Time:** 8-12 hours  
**Status:** 🟡 MEDIUM PRIORITY (for 50-100 repo ecosystem)

**Implementation Tasks:**
- [ ] **Batch Processing Pipeline:**
  - Process multiple repositories in parallel
  - Track cross-repository dependencies
  - Identify shared business components
  - Generate ecosystem-wide business domain map

- [ ] **Business Dependency Detection:**
  - CORBA service calls across repositories
  - Shared Struts action forwards
  - Common business rule patterns
  - Data model dependencies

- [ ] **Migration Impact Analysis:**
  - Repository interdependency mapping
  - Migration priority scoring based on dependencies
  - Risk assessment for breaking changes
  - Shared component migration templates

**Success Criteria:**
- System can process 50+ repositories efficiently
- Cross-repository business dependencies visible in graph
- Migration impact analysis available for planning

---

### **T3.3: Migration Planner Enhancement**
**Assignee:** Development Team + Business Analyst  
**Estimated Time:** 6-10 hours  
**Status:** 🟡 LOW PRIORITY (can be done later)

**Implementation Tasks:**
- [ ] **Migration Templates:**
  - Struts Action → GraphQL Mutation/Query patterns
  - JSP → Angular Component conversion templates  
  - CORBA Interface → GraphQL Service mappings
  - Business Rule → Validation Service patterns

- [ ] **Complexity-Based Planning:**
  - Effort estimation based on business analysis
  - Risk scoring for migration complexity
  - Dependency-aware migration sequencing
  - Resource allocation recommendations

- [ ] **Migration Progress Tracking:**
  - Component-level migration status
  - Business rule migration verification
  - Cross-repository migration coordination
  - Rollback and risk mitigation planning

---

### **T3.4: Strands Agent Business Context Integration**
**Assignee:** Development Team  
**Estimated Time:** 3-4 hours  
**Status:** 🟡 LOW PRIORITY

**Implementation Tasks:**
- [ ] **Enhanced Agent Prompts:**
  - Include business context in agent system prompts
  - Add migration-specific question handling
  - Reference business components in responses
  - Provide framework-specific migration guidance

- [ ] **Business Query Capabilities:**
  - Query business rules by domain
  - Find components by migration complexity
  - Trace business relationships across files
  - Generate migration recommendations

**Success Criteria:**
- Agent can answer golden questions with business context
- Agent references specific business components
- Agent provides migration-focused recommendations

---

## **🚀 PRIORITY 4: PRODUCTION READINESS**

### **T4.1: Error Handling & Resilience**
**Assignee:** Development Team  
**Estimated Time:** 4-6 hours  
**Status:** 🟡 MEDIUM PRIORITY

**Implementation Tasks:**
- [ ] **Enhanced Parser Error Recovery:**
  - Graceful handling of malformed JSP/XML
  - Partial business analysis on parser errors
  - Logging and diagnostics for unsupported patterns
  - Fallback to basic file indexing on analysis failure

- [ ] **Neo4j Transaction Management:**
  - Atomic business component creation
  - Rollback on relationship creation failure
  - Duplicate business rule detection and merging
  - Performance optimization for large batches

- [ ] **Processing Pipeline Resilience:**
  - Retry logic for transient failures
  - Progress checkpointing for large repositories
  - Memory management for business analysis
  - Timeout handling for complex legacy codebases

---

### **T4.2: Performance Optimization**
**Assignee:** Development Team  
**Estimated Time:** 6-8 hours  
**Status:** 🟡 LOW PRIORITY

**Optimization Tasks:**
- [ ] **Business Analysis Caching:**
  - Cache business patterns between processing runs
  - Incremental analysis for changed files only
  - Shared business rule detection across repositories
  - Framework pattern template caching

- [ ] **Neo4j Query Optimization:**
  - Index optimization for business queries
  - Query plan analysis for graph visualization
  - Batch insertion optimization for business components
  - Memory usage optimization for large graphs

- [ ] **Parallel Processing Enhancement:**
  - Multi-threaded business analysis
  - Concurrent Neo4j writes with conflict resolution
  - Repository processing pipeline optimization
  - Resource usage monitoring and throttling

---

### **T4.3: Monitoring & Observability**
**Assignee:** Development Team  
**Estimated Time:** 3-4 hours  
**Status:** 🟡 LOW PRIORITY

**Implementation Tasks:**
- [ ] **Business Analysis Metrics:**
  - Business rule extraction success rates
  - Framework pattern recognition accuracy
  - Migration complexity distribution
  - Processing time by repository size/complexity

- [ ] **Quality Metrics:**
  - Business relationship accuracy validation
  - Migration complexity score validation
  - User satisfaction with business context
  - False positive rates in business rule detection

- [ ] **Performance Monitoring:**
  - Business analysis processing time
  - Neo4j business query performance
  - Graph visualization load times
  - Memory usage during legacy framework parsing

---

## **📊 IMPLEMENTATION PRIORITY MATRIX**

| Priority | Category | Tasks | Total Effort | Business Impact |
|----------|----------|-------|-------------|-----------------|
| **P1** | Testing & Validation | T1.1-T1.4 | 4-6 hours | 🔴 CRITICAL |
| **P2** | Documentation | T2.1-T2.4 | 15-21 hours | 🟡 HIGH |
| **P3** | Implementation | T3.1-T3.4 | 21-32 hours | 🟡 MEDIUM |
| **P4** | Production Ready | T4.1-T4.3 | 13-18 hours | 🟡 LOW |

**Total Estimated Effort:** 53-77 hours

---

## **🎯 RECOMMENDED EXECUTION SEQUENCE**

### **Week 1: Validation & Core Documentation**
- **Day 1-2:** Complete T1.1-T1.4 (Testing & Validation)
- **Day 3-5:** T2.1-T2.2 (Architecture & API Documentation)

### **Week 2: User Documentation & ChromaDB**  
- **Day 1-3:** T2.3-T2.4 (User Guide & Developer Setup)
- **Day 4-5:** T3.1 (ChromaDB Business Integration)

### **Week 3+: Advanced Features** (Optional)
- T3.2-T3.4 (Cross-Repo Analysis, Migration Planner, Agent Enhancement)
- T4.1-T4.3 (Production Hardening)

---

## **📋 KIRO'S SPECIFIC DOCUMENTATION FOCUS**

**Primary Responsibilities:**
1. **T2.1:** System Architecture Documentation (4-6 hours)
2. **T2.2:** API Documentation Updates (3-4 hours)
3. **T2.3:** User Guide Creation (6-8 hours) 
4. **T2.4:** Developer Setup Guide (2-3 hours)

**Secondary Support:**
- Review and validate T1.4 (Golden Questions Testing)
- Collaborate on T3.4 (Agent Enhancement) for documentation

**Total Kiro Effort:** 15-21 hours over 1-2 weeks

This detailed TODO provides clear scope, effort estimates, and priority guidance for both immediate validation and comprehensive documentation of the enhanced ingestion system.