--- 
paths: 
    - "**/*.py" 
    - "**/*.pyi" 
--- 

# Python Patterns 

- Prefer existing LAEW patterns before introducing new ones. 
- Use `Protocol` for real structural interfaces. 
- Use `dataclass` for lightweight data objects when appropriate. 
- Use context managers for resource lifetime management. 
- Use generators for naturally lazy or streaming operations. 
- Avoid unnecessary wrapper classes and abstractions. 
- Prefer explicit, readable control flow over clever metaprogramming.