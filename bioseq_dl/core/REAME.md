## List of things to do

- [ ] In uniprot.py, line 413, change `self.parse(response.json(), extract_fields)` to `self.parse(response, extract_fields)` because sometimes the response is not json serializable. To handle both cases we can make sure that the response is a json object before calling `response.json()`.
- [ ] In uniprot.py, auto_db=True in method `download_batch` is not working as intended. Also the presence of this parameter doesnt make `from_db` and `to_db` parameters necessary. We can make optional.
- [ ] Add docstrings to `download_batch` method in uniprot.py
- [ ] for uniprot.py in method `submit_stream` parameters like include_isoform, download, format should have default values and have a better docstring explaining their purpose.
- [ ] In workflow/main_workflow.py, line 247, the parameter `pages_to_fetch=-1` and `limit=100` should be explained in a comment or docstring to clarify their purpose.
- [ ] IN workflow/main_workflow.py when a large number of chembl ids are requested, the search fails. Implement pagination to handle large requests.