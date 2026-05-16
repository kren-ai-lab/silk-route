import os

from typing import Union, List, Dict, Set, Optional

import pandas as pd

from .base import BaseAPIInterface
# Add the import for your database in constants
from ...constants.databases import YOUR_DATABASE

class YourDatabaseInterface(BaseAPIInterface):
    def __init__(
            self,  
            cache_dir: Optional[str] = None,
            config_dir: Optional[str] = None,
            output_dir: Optional[str] = None,
            **kwargs
        ):

        if cache_dir:
            cache_dir = os.path.abspath(cache_dir)
        else:
            cache_dir = YOUR_DATABASE.CACHE_DIR if YOUR_DATABASE.CACHE_DIR is not None else ""

        if config_dir is None:
            config_dir = YOUR_DATABASE.CONFIG_DIR if YOUR_DATABASE.CONFIG_DIR is not None else ""

        super().__init__(cache_dir=cache_dir, config_dir=config_dir, **kwargs)
        self.output_dir = output_dir or cache_dir
        os.makedirs(self.output_dir, exist_ok=True)

    # def get_cache_ignore_keys(self) -> Set[str]:
    #     return super().get_cache_ignore_keys().union({"ID_TO_IGNORE", "ID2_TO_IGNORE"})
    
    # def get_subquery_match_keys(self) -> Set[str]:
    #     return super().get_subquery_match_keys().union({"KEY_TO_MATCH", "ANOTHER_KEY_TO_MATCH"})


    def fetch(
            self, 
            query: Union[str, dict, list], 
            *, 
            method: str = "SOME_DEFAULT", 
            **kwargs
        ):
        raise NotImplementedError("This method should be implemented in subclasses.")
    
        try:
            response = self.session.get(url)
            self._delay()
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching prediction for {query}: {e}")
            return {}
        
    def parse(
            self, 
            data: Union[List, Dict],
            fields_to_extract: Optional[Union[list, dict]],
            **kwargs
        ) -> Union[List, Dict]:
        raise NotImplementedError("This method should be implemented in subclasses.")
    
    def query_usage(self) -> str:
        return "Query usage information has not been customized for this interface template."
    
