// Toolbar: removes the import button, adds the bookmarks-toolbar toggle
// button and keeps its checked state in sync, and lays out a new profile's
// navigation bar.
(function (MyFox) {
  const { prefs, t, oncePerProfile, whenDelayedStartupDone } = MyFox;

  // A new profile gets our navigation-bar layout once; a profile whose layout
  // Firefox has already saved keeps it (the user may have arranged it). Read
  // now, before Firefox saves a layout for this start.
  let arrangeNavBar = false;
  oncePerProfile("myfox.navBarLayoutInitialized", () => {
    arrangeNavBar = !prefs.prefHasUserValue("browser.uiCustomization.state");
  });

  // Back and forward right before the address bar, reload right after it, so
  // Firefox's two springs center the group; no Home button. The other
  // buttons stay where Firefox puts them.
  function arrangeNavBarOnce(CustomizableUI) {
    if (!arrangeNavBar) return;
    arrangeNavBar = false;
    const area = CustomizableUI.AREA_NAVBAR;
    const indexOf = id => CustomizableUI.getWidgetIdsInArea(area).indexOf(id);
    try {
      if (indexOf("home-button") !== -1) CustomizableUI.removeWidgetFromArea("home-button");
      for (let id of ["back-button", "forward-button"]) {
        if (indexOf(id) !== -1) CustomizableUI.moveWidgetWithinArea(id, indexOf("urlbar-container"));
      }
      if (indexOf("stop-reload-button") !== -1) {
        CustomizableUI.moveWidgetWithinArea("stop-reload-button", indexOf("urlbar-container") + 1);
      }
    } catch(e) {}
  }

  function initWindow(win) {
    const doc = win.document;
    const sbCtrl = win.SidebarController;
    const CustomizableUI = win.CustomizableUI;

    // Profile-local replacement for the DisableProfileImport policy (we
    // never install policies): Firefox adds an "Import bookmarks"
    // (import-button) widget to the toolbar — catch its addition and
    // remove it right away. The profile button is hidden by the
    // identity.fxaccounts.toolbar.enabled default above.
    let myfoxHiddenWidgets = ["import-button"];
    try {
      if (!globalThis.myHiddenWidgetsListener) {
        globalThis.myHiddenWidgetsListener = {
          onWidgetAdded(widgetId) {
            if (myfoxHiddenWidgets.includes(widgetId)) {
              try { CustomizableUI.removeWidgetFromArea(widgetId); } catch(e) {}
            }
          }
        };
        CustomizableUI.addListener(globalThis.myHiddenWidgetsListener);
      }
      for (let wg of myfoxHiddenWidgets) {
        try { CustomizableUI.removeWidgetFromArea(wg); } catch(e) {}
      }
    } catch(e) {}

    function registerWidget() {
      try {
        if (CustomizableUI) {
          let widget = CustomizableUI.getWidget("toggle-bookmarks-toolbar-button");
          if (widget && widget.provider !== "api") {
            CustomizableUI.destroyWidget("toggle-bookmarks-toolbar-button");
            widget = null;
          }

          if (!widget) {
            CustomizableUI.createWidget({
              id: "toggle-bookmarks-toolbar-button",
              label: t("toolbar.bookmarks.label"),
              tooltiptext: t("toolbar.bookmarks.tooltip"),
              localized: false,
              onCreated(button) {
                const win = button.ownerDocument.defaultView;
                button.setAttribute("class", "toolbarbutton-1 chromeclass-toolbar-additional");
                button.style.listStyleImage = "url('chrome://browser/skin/places/bookmarksToolbar.svg')";
                button.style.fill = "currentColor";
                button.style.mozContextProperties = "fill, fill-opacity, stroke, stroke-opacity";

                const personalToolbar = button.ownerDocument.getElementById("PersonalToolbar");
                if (personalToolbar) {
                  button.toggleAttribute("checked", !personalToolbar.collapsed);
                }

                button.addEventListener("command", (e) => {
                  const personalToolbar = button.ownerDocument.getElementById("PersonalToolbar");
                  if (personalToolbar) {
                    let currentlyCollapsed = personalToolbar.collapsed;
                    CustomizableUI.setToolbarVisibility("PersonalToolbar", currentlyCollapsed);
                  }
                });
              }
            });
          }

          function ensurePlacement() {
            try {
              let placement = CustomizableUI.getPlacementOfWidget("toggle-bookmarks-toolbar-button");
              if (!placement) {
                let position = 1;
                let areaWidgets = CustomizableUI.getWidgetsInArea(CustomizableUI.AREA_NAVBAR);
                for (let i = 0; i < areaWidgets.length; i++) {
                  if (areaWidgets[i].id === "sidebar-button") {
                    position = i + 1;
                    break;
                  }
                }
                CustomizableUI.addWidgetToArea(
                  "toggle-bookmarks-toolbar-button",
                  CustomizableUI.AREA_NAVBAR,
                  position
                );
              }
            } catch(e) {}
            arrangeNavBarOnce(CustomizableUI);
          }

          whenDelayedStartupDone(win, ensurePlacement);
        }
      } catch(ex) {}
    }

    function setupBookmarksToolbarObserver() {
      try {
        const personalToolbar = doc.getElementById("PersonalToolbar");
        if (!personalToolbar) return;

        const updateBtnState = () => {
          const btn = doc.getElementById("toggle-bookmarks-toolbar-button");
          if (btn) {
            btn.toggleAttribute("checked", !personalToolbar.collapsed);
          }
        };

        updateBtnState();

        const obs = new win.MutationObserver((mutations) => {
          for (let mutation of mutations) {
            if (mutation.attributeName === "collapsed") {
              updateBtnState();
            }
          }
        });
        obs.observe(personalToolbar, {
          attributes: true,
          attributeFilter: ["collapsed"]
        });

        win.myBookmarksToolbarObserver = obs;
      } catch(e) {}
    }

    if (CustomizableUI) {
      registerWidget();
    } else {
      win.addEventListener("load", function onLoadWidget() {
        win.removeEventListener("load", onLoadWidget);
        registerWidget();
      });
    }

    whenDelayedStartupDone(win, setupBookmarksToolbarObserver);
  }
  MyFox.windowInits.push(initWindow);
})(globalThis.MyFox);
