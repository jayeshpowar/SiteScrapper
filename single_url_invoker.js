var system = require('system');
var args = system.args;
var fs = require('fs');


var page = require('webpage').create();

var destProducts = [];
var errorCodes = [403,404,500,505];
var file_name = args[1];
var srcProducts = fs.read(file_name, 'utf8').trim().split("\n");

var errorCodes = [403,404,500,505];

page.settings.resourceTimeout = 30000; // 15 seconds

function visit(url , file_name){
      console.log("Remaining Urls : " +srcProducts.length + " for "+file_name);
      var page = new WebPage();
      page.address = url;
      page.brokenResources = new Array();
      page.errors = new Array();
      //console.log('visiting '+url );
        page.onResourceReceived = function (resource) {

              if (resource.stage === 'end') {
                url = resource.url;
                if(resource.url.indexOf('data')>=0){
                  url = 'data(...)';
                }
                if(errorCodes.indexOf(resource.status)>=0){
                   console.log('{"broken-resource":"'+url+'","parent":"'+page.url+'"}');
                }
              }
        };

        page.onError = function(msg, trace) {
             console.log('{"error":"'+msg+'","parent":"'+page.url+'"}');
        };

        page.open(page.address, function (status) {

                if (status !== 'success') {
                    console.log('FAIL to load the address '+ page.address);
                }else{


                   page.close();

                   if(srcProducts.length > 2){
                        var url = srcProducts.pop();
                        visit(url, file_name);

                   }else{
                         phantom.exit();
                   }

              }
        });


}

if (args.length === 1) {
  console.log('Try to pass some arguments when invoking this script!');
  phantom.exit();
}
var busy =false;

//while (srcProducts.length != 0) {
    var url = srcProducts.pop();
    visit(url,file_name);
//  }

 //phantom.exit();


