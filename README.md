Install the dependencies using
===================================
pip install -r requirements.txt

Before installing requirements make sure your system has libffi-dev and
libssl-dev libraries installed .

Start scrapping  by executing
===================================
python Scrapper.py 'http://www.example.com'

Limitations
============
1.Currently the utility doesn't scrape the pages obtained after loggging in .

2.Handling localhost based urls might require some tweaking .