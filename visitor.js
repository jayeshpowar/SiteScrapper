var page = require('webpage').create();
var system = require('system');
var args = system.args;

if (args.length === 1) {
  console.log('Try to pass some arguments when invoking this script!');
  phantom.exit();
}

var url = args[1]


page.onConsoleMessage = function(msg) {
  console.log(msg);
};

page.onError = function(msg, trace) {
    var msgStack = ['ERROR: ' + msg];
    /*if (trace && trace.length) {
        msgStack.push('TRACE:');
        trace.forEach(function(t) {
            msgStack.push(' -> ' + t.file + ': ' + t.line + (t.function ? ' (in function "' + t.function + '")' : ''));
        });
    }*/
    console.error(msgStack);
};

page.open(url , function(status) {
    // console.log(status + ' : ' + page.url);
    phantom.exit();
});
