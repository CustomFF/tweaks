// `firefox-myfox --myfox-restart`: MyFox runs this after it updated the tweaks
// on disk, since autoconfig and chrome/ are read only at startup. Firefox's
// remoting hands the command line to the instance already running this
// profile, which then restarts itself the way about:profiles' "Restart" does
// (and SessionStore restores the session once, as after any restart).
(function (MyFox) {
  const { Cc, Ci, os } = MyFox;
  const CONTRACT_ID = "@customff.github.io/myfox/restart-clh;1";
  const CID = Components.ID("{5b9c0199-574f-40bc-9e56-cef6e33ab14e}");

  const registrar = Components.manager.QueryInterface(Ci.nsIComponentRegistrar);

  function restart() {
    // Listeners may cancel: unsubmitted forms, running downloads, the
    // "close N tabs?" prompt.
    let cancelQuit = Cc["@mozilla.org/supports-PRBool;1"].createInstance(Ci.nsISupportsPRBool);
    os.notifyObservers(cancelQuit, "quit-application-requested", "restart");
    if (cancelQuit.data) return;
    Services.startup.quit(Ci.nsIAppStartup.eAttemptQuit | Ci.nsIAppStartup.eRestart);
  }

  const handler = {
    handle(cmdLine) {
      if (!cmdLine.handleFlag("myfox-restart", false)) return;
      // Firefox wasn't running, so this launch already reads the new files.
      // A restart also relaunches with the first launch's arguments, so this
      // is what keeps a restart from looping.
      if (cmdLine.state === Ci.nsICommandLine.STATE_INITIAL_LAUNCH) return;
      // No new window or tab for this command line.
      cmdLine.preventDefault = true;
      // Outside the remote command's handling: the quit prompts spin a
      // nested event loop.
      Services.tm.dispatchToMainThread(restart);
    },
    helpInfo: "  --myfox-restart    Restart the running MyFox Firefox.\n",
    QueryInterface: ChromeUtils.generateQI(["nsICommandLineHandler"]),
  };

  registrar.registerFactory(CID, "MyFox restart command line handler", CONTRACT_ID, {
    createInstance(iid) { return handler.QueryInterface(iid); },
    QueryInterface: ChromeUtils.generateQI(["nsIFactory"]),
  });
  // Handlers run in entry order: before "m-browser", which would otherwise
  // open a window for this command line.
  Services.catMan.addCategoryEntry("command-line-handler", "a-myfox-restart", CONTRACT_ID, false, true);
})(globalThis.MyFox);
