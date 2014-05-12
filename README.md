Install the dependencies using
===================================
pip install -r requirements.txt

Before installing requirements make sure your system has libffi-dev and
libssl-dev libraries installed .

Start scrapping  by executing
===================================
python Scrapper.py 'http://www.example.com'

To scrape the site using the twisted version of the library execute :

python my_twisted_scrapper.py 'http://www.example.com'

The twisted version spawns quite large number of connections on the server \n
resulting in conditions similar to DOS and might leat to pages returning 503 \n
 errors. In such scenarios modify the max concurrent connections settings in the
   \n config.ini file .


Limitations
============
1.Currently the utility doesn't scrape the pages obtained after loggging in .

2.Handling localhost based urls might require some tweaking .