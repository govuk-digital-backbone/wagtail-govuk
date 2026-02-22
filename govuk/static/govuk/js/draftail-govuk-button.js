(function initGovukButtonDraftailPlugin() {
  if (!window.draftail || !window.draftail.registerPlugin) {
    return;
  }

  if (!window.React || !window.draftail.TooltipEntity) {
    return;
  }

  if (!window.draftail.LinkModalWorkflowSource) {
    return;
  }

  function createDecorator(label) {
    return function GovukButtonDecorator(props) {
      var entity = props.contentState.getEntity(props.entityKey);
      var data = entity.getData() || {};

      return window.React.createElement(
        window.draftail.TooltipEntity,
        Object.assign({}, props, {
          icon: "link",
          label: label,
          url: data.url || "",
        }),
        props.children
      );
    };
  }

  window.draftail.registerPlugin(
    {
      type: "GOVUK_BUTTON_LINK",
      source: window.draftail.LinkModalWorkflowSource,
      decorator: createDecorator("Button link"),
    },
    "entityTypes"
  );

  window.draftail.registerPlugin(
    {
      type: "GOVUK_START_BUTTON_LINK",
      source: window.draftail.LinkModalWorkflowSource,
      decorator: createDecorator("Start button link"),
    },
    "entityTypes"
  );
})();
