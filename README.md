# reco

A simple proof-of-concept for doing artist/band recommendations using only user-submitted information.

## How to use

First initialize the sqlite database. Call init_db() from the python interpreter:

```python
from reco import init_db
init_db()
```

Start a local instance:

```python
python reco.py
```
