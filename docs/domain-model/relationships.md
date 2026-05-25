# Relationships

  - Program → ProgramStatus (many-to-one, lazy=joined, RESTRICT on delete)
  - Program → WorkItem (one-to-many, cascade all+delete-orphan) 
  - Program → Dependency (one-to-many, cascade all+delete-orphan)
  - WorkItem → SourceType (many-to-one, SET NULL on delete)