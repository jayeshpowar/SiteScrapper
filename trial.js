var system = require('system');
var args = system.args;
var fs = require('fs');

var errorCodes = [403,404,500,505];

function visit(url, callback){
      var page = new WebPage();
      page.address = url;
      page.brokenResources = new Array();
      page.errors = new Array();

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

                    callback.apply();
              }
        });


}

if (args.length === 1) {
  console.log('Try to pass some arguments when invoking this script!');
  phantom.exit();
}

var line_count = 0;

function process(){


        var url = file_h.readLine();

       // while(line_count % line_index !=0){
       //     line_count = line_count + 1 ;
       // }
       // if (line_count >= fileArrData.length){
       //    phantom.exit();
       // }else{
             //var url = fileArrData[line_count];
             if (url) {
                visit(url,process);
                url = file_h.readLine();
             }else{
               file_h.close();
               phantom.exit();

             }
       //  }


}

var file_name = args[1];
//var line_index = args[2]
var file_h = fs.open(file_name, 'r');

//var filedata = fs.read(file_name)
//var fileArrData = filedata.split('\n');
process();
