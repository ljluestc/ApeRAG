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

from typing import Any, Dict, List, TypeVar

from aperag.schema.view_models import OffsetPaginatedResponse

T = TypeVar("T")


class OffsetPaginationHelper:
    """Helper class for offset-based pagination"""

    @staticmethod
    def build_response(
        items: List[T], 
        total: int, 
        offset: int, 
        limit: int
    ) -> OffsetPaginatedResponse[T]:
        """
        Build offset-based paginated response.
        
        Args:
            items: List of items for the current page
            total: Total number of items available
            offset: Offset that was used for this request
            limit: Limit that was used for this request
            
        Returns:
            OffsetPaginatedResponse with the requested structure
        """
        return OffsetPaginatedResponse(
            total=total,
            limit=limit,
            offset=offset,
            data=items
        )

    @staticmethod
    def convert_page_to_offset(page: int, page_size: int) -> int:
        """
        Convert page-based pagination to offset-based pagination.
        
        Args:
            page: Page number (1-based)
            page_size: Number of items per page
            
        Returns:
            Offset value (0-based)
        """
        return (page - 1) * page_size

    @staticmethod
    def convert_offset_to_page(offset: int, limit: int) -> int:
        """
        Convert offset-based pagination to page-based pagination.
        
        Args:
            offset: Offset value (0-based)
            limit: Number of items per page
            
        Returns:
            Page number (1-based)
        """
        return (offset // limit) + 1
