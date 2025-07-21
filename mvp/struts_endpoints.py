# Struts-specific endpoints for legacy application migration

@app.post("/struts/analyze")
async def analyze_struts_repository(request: IndexRequest):
    """Analyze a Struts application repository for migration planning."""
    if not struts_parser:
        raise HTTPException(status_code=500, detail="Struts parser not initialized")
    
    try:
        repo_path = Path(request.repo_path)
        
        # Validate repository path
        if not repo_path.exists():
            raise HTTPException(status_code=404, detail=f"Repository path not found: {request.repo_path}")
        
        # Analyze Struts application
        repo_name = request.repo_name or repo_path.name
        analysis = struts_parser.analyze_struts_application(str(repo_path))
        
        return {
            "status": "success",
            "repository": repo_name,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Failed to analyze Struts repository: {e}")
        raise HTTPException(status_code=500, detail=f"Struts analysis failed: {str(e)}")


@app.get("/struts/actions")
async def get_struts_actions(
    repository: Optional[str] = Query(None, description="Filter by repository")
):
    """Get all Struts actions discovered in indexed repositories."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        # Search for Struts Action classes
        query = "extends Action execute method ActionForward"
        if repository:
            query += f" repository:{repository}"
        
        results = await search.search(
            query=query,
            limit=100,
            similarity_threshold=0.6
        )
        
        # Process results to extract action information
        actions = []
        for result in results:
            if "Action" in result["file_path"] and ".java" in result["file_path"]:
                actions.append({
                    "file_path": result["file_path"],
                    "class_name": Path(result["file_path"]).stem,
                    "score": result["score"],
                    "content_preview": result["content"][:200] + "..."
                })
        
        return {
            "actions": actions,
            "total": len(actions),
            "repository": repository
        }
        
    except Exception as e:
        logger.error(f"Failed to get Struts actions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get actions: {str(e)}")


@app.get("/struts/forms")
async def get_struts_forms(
    repository: Optional[str] = Query(None, description="Filter by repository")
):
    """Get all Struts form beans discovered in indexed repositories."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        # Search for Struts Form classes
        query = "extends ActionForm DynaActionForm ValidatorForm"
        if repository:
            query += f" repository:{repository}"
        
        results = await search.search(
            query=query,
            limit=100,
            similarity_threshold=0.6
        )
        
        # Process results to extract form information
        forms = []
        for result in results:
            if "Form" in result["file_path"] and ".java" in result["file_path"]:
                forms.append({
                    "file_path": result["file_path"],
                    "class_name": Path(result["file_path"]).stem,
                    "score": result["score"],
                    "content_preview": result["content"][:200] + "..."
                })
        
        return {
            "forms": forms,
            "total": len(forms),
            "repository": repository
        }
        
    except Exception as e:
        logger.error(f"Failed to get Struts forms: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get forms: {str(e)}")


@app.get("/struts/jsps")
async def get_struts_jsps(
    repository: Optional[str] = Query(None, description="Filter by repository")
):
    """Get all JSP files with Struts tags discovered in indexed repositories."""
    if not search:
        raise HTTPException(status_code=500, detail="Search not initialized")
    
    try:
        # Search for JSP files with Struts tags
        query = "html:form bean:write logic:iterate struts tags"
        if repository:
            query += f" repository:{repository}"
        
        results = await search.search(
            query=query,
            limit=100,
            similarity_threshold=0.5
        )
        
        # Process results to extract JSP information
        jsps = []
        for result in results:
            if ".jsp" in result["file_path"] or ".tag" in result["file_path"]:
                jsps.append({
                    "file_path": result["file_path"],
                    "score": result["score"],
                    "content_preview": result["content"][:200] + "..."
                })
        
        return {
            "jsps": jsps,
            "total": len(jsps),
            "repository": repository
        }
        
    except Exception as e:
        logger.error(f"Failed to get Struts JSPs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get JSPs: {str(e)}")


@app.get("/struts/migration-plan/{repository}")
async def generate_migration_plan(repository: str):
    """Generate a GraphQL migration plan for a Struts repository."""
    if not search or not struts_parser:
        raise HTTPException(status_code=500, detail="Required components not initialized")
    
    try:
        # Analyze business logic patterns
        business_logic_query = "business logic validation calculate process transform"
        business_results = await search.search(
            query=f"{business_logic_query} repository:{repository}",
            limit=50,
            similarity_threshold=0.6
        )
        
        # Analyze data models
        data_model_query = "data model DTO bean entity form"
        data_results = await search.search(
            query=f"{data_model_query} repository:{repository}",
            limit=50,
            similarity_threshold=0.6
        )
        
        # Analyze endpoints/actions
        endpoint_query = "action mapping execute method path forward"
        endpoint_results = await search.search(
            query=f"{endpoint_query} repository:{repository}",
            limit=50,
            similarity_threshold=0.6
        )
        
        # Generate migration suggestions
        migration_plan = {
            "repository": repository,
            "analysis_summary": {
                "business_logic_components": len(business_results),
                "data_models_found": len(data_results),
                "endpoints_discovered": len(endpoint_results)
            },
            "graphql_suggestions": {
                "recommended_types": [],
                "recommended_queries": [],
                "recommended_mutations": [],
                "business_logic_resolvers": []
            },
            "migration_steps": [
                "1. Analyze discovered business logic components",
                "2. Design GraphQL schema from data models",
                "3. Map Struts actions to GraphQL operations",
                "4. Implement resolvers with extracted business logic",
                "5. Test migration incrementally"
            ]
        }
        
        # Extract suggested GraphQL types from data models
        for result in data_results[:10]:
            file_name = Path(result["file_path"]).stem
            if "Form" in file_name or "DTO" in file_name or "Bean" in file_name:
                type_name = file_name.replace("Form", "").replace("DTO", "").replace("Bean", "")
                migration_plan["graphql_suggestions"]["recommended_types"].append(type_name)
        
        # Extract suggested queries/mutations from actions
        for result in endpoint_results[:10]:
            content = result["content"].lower()
            file_name = Path(result["file_path"]).stem
            
            if any(keyword in content for keyword in ["get", "find", "search", "list"]):
                migration_plan["graphql_suggestions"]["recommended_queries"].append(
                    f"get{file_name.replace('Action', '')}"
                )
            elif any(keyword in content for keyword in ["save", "update", "create", "delete"]):
                migration_plan["graphql_suggestions"]["recommended_mutations"].append(
                    f"update{file_name.replace('Action', '')}"
                )
        
        return migration_plan
        
    except Exception as e:
        logger.error(f"Failed to generate migration plan: {e}")
        raise HTTPException(status_code=500, detail=f"Migration plan generation failed: {str(e)}")