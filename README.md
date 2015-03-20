# reco

A simple proof-of-concept for doing artist/band recommendations using only user-submitted information.

## How to use

Clone this repository. Then, create a Python virtual environment for this project and activate it:

```bash
virtualenv venv
source venv/bin/activate
```

Install the requirements (you may need to install pip first):

```bash
pip install requirements.txt
```

Initialize the sqlite database. Call init_db() from the python interpreter:

```python
from reco import init_db
init_db()
```

For fetching album covers from Discogs you will need to sign up for a Discogs account and create a new application to get an API consumer key and consumer secret. Add your consumer key, consumer secret and user agent to config.py.

Start a local instance:

```bash
python reco.py
```
