var page = require('webpage').create();
var system = require('system');
var args = system.args;
var fs = require('fs');

if (args.length === 1) {
  console.log('Try to pass some arguments when invoking this script!');
  phantom.exit();
}

function visit(url, callback){
      page = require('webpage').create()

      page.onLoadFinished = function(status) {
        page.close();
        callback.apply();
      };

      page.onError = function(msg, trace,url) {
          var msgStack = ['ERROR: ' + msg];
          console.error('errors '+msgStack);
      };

      var statusCodes = [200,304,302,301,303,201]
      page.onResourceReceived = function (res, url) {
          if(statusCodes.indexOf(res.status)<0 && res.status !=null && res.stage == 'end'  ){
            console.log('Error loading : ' + res.url + ' with status : '+ res.status+ ' for  '+page.url);
          }
      };

      page.open(url , function(status) {
        if (status === 'success') {
            // console.log('Examining url ' + url );
        }
      });
}

function process(){
    var url = file_h.readLine();
    print(url);
     if (url) {
        visit(url,process);
        url = file_h.readLine();
     }else{
       file_h.close();
       phantom.exit();

     }
}

var file_h = fs.open(args[1], 'r');
process();
