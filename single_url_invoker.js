var system = require('system');
var args = system.args;
var fs = require('fs');

var errorCodes = [403,404,500,505];

function visit(url){
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
                    page.brokenResources.push(url);
                }
              }
        };

        page.onError = function(msg, trace) {
          page.errors.push(msg);
        };

        page.open(page.address, function (status) {

                if (status !== 'success') {
                    console.log('FAIL to load the address '+ page.address);
                }else{

                    var arrayLength = page.errors.length;
                    var resourcesLength = page.brokenResources.length;

                    if( arrayLength >0 || resourcesLength >0 ){
                         console.log('\n\nExamined page '+page.address);
                    }

                    if( arrayLength >0 ){
                        console.log("Errors found :")
                          for (var i = 0; i < arrayLength; i++) {
                            console.log(page.errors[i]);
                          }
                    }



                    if( resourcesLength >0 ){
                      console.log("Broken Resources found : ");
                        for (var i = 0; i < resourcesLength; i++) {
                            console.log(page.brokenResources[i]);
                        }
                    }
                 //  console.log('visited '+url );
                   page.close();
                   phantom.exit();
              }
        });


}

if (args.length === 1) {
  console.log('Try to pass some arguments when invoking this script!');
  phantom.exit();
}



var url = args[1];
visit(url);

