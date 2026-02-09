
from typing import List, Optional
from pydantic import BaseModel

class InheritNode(BaseModel):
    name: str
    package: Optional[str] = None
    superclass: Optional[str] = None
    interfaces: List[str] = []
    file_path: str
