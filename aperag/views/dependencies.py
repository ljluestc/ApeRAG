# Copyright 2025 ApeCloud, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import Dict, Optional

from fastapi import Query


def pagination_params(
    offset: int = Query(0, ge=0, description="Number of items to skip from the beginning"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of items to return"),
) -> Dict[str, int]:
    """
    FastAPI dependency for pagination parameters.
    
    Enforces a maximum limit of 100 to protect the server from abusive requests.
    If a client requests a limit greater than the maximum, the API caps it at 100.
    
    Args:
        offset: Number of items to skip from the beginning of the list
        limit: Maximum number of items to return in the response
        
    Returns:
        Dictionary containing offset and limit values
    """
    # Enforce maximum limit
    if limit > 100:
        limit = 100
    
    return {"offset": offset, "limit": limit}


def page_pagination_params(
    page: int = Query(1, ge=1, description="Page number (1-based)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page"),
) -> Dict[str, int]:
    """
    FastAPI dependency for page-based pagination parameters.
    
    This is an alternative to offset-based pagination that some endpoints might prefer.
    
    Args:
        page: Page number (1-based)
        page_size: Number of items per page
        
    Returns:
        Dictionary containing page and page_size values
    """
    # Enforce maximum page size
    if page_size > 100:
        page_size = 100
    
    return {"page": page, "page_size": page_size}
