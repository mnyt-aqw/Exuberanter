// Setup the required environment with the following command after
// building the WPD program using the official build instructions.
//
// ln -s ../../output/interface/digitizer ./WebPlotDigitizer/app/
//
// The images are exported through the `interface.py` script and then
// automatically loaded in wpd if a local instance is run with this script
// added.
//
// For instructions on building WPD, see the web server part of
// https://github.com/ankitrohatgi/WebPlotDigitizer/blob/master/DEVELOPER_GUIDELINES.md#building-source
var wpdscript = (function () {
  function run() {
    // Start listening for changes in the image, representing a new image and
    // then do a hot-reload
    check_for_image();
  }

  // Listen for changes in real-time and update image on change
  var previous_response = null;
  function check_for_image() {
    let xhr = new XMLHttpRequest();
    xhr.onload = function() {
      if (previous_response != xhr.response) {
        response = JSON.parse(xhr.response);
        console.log(`New image detected, loading ${response['path']}...`);
        wpd.imageManager.loadFromURL(response['path']);
      }

      previous_response = xhr.response;
    };

    xhr.open('GET', '/digitizer/digitizer.json');
    xhr.send();

    // Check again on a 1000ms interval
    setTimeout(check_for_image, 100);
  }

  return {
    run: run
  };
})();
