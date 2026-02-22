"""Pydantic v2 request schemas for Flask blueprint validation.

Each sub-module corresponds to a blueprint in frontend/blueprints/.
Use model_validate(request.get_json() or {}) at the start of POST handlers
and return a 422 with the validation errors on ValidationError.
"""
