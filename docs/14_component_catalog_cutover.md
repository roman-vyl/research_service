# Component Catalog cutover

The Workbench endpoint `/api/research/component-catalog` is now backed by Strategy Engine's `/v1/strategies/{strategy_id}/composer-catalog` endpoint. The exact BBB `ComponentCatalog` DTO remains the BFF response contract. The result is validated with Pydantic and cached for the application lifetime. Strategy semantics are no longer authored in Research Service.
