// client side graph rendering logic

(function () {
    function getIsDark() {
        return document.documentElement.dataset.theme === "dark";
    }




    function applyThemeToLayout(layout) {
        const isDark = getIsDark();
        const fontColor = isDark ? "#ecede9" : "#1c1d1f";
        const gridColor = isDark ? "rgba(255, 255, 255, 0.08)" : "rgba(0, 0, 0, 0.08)";
        const zeroLineColor = isDark ? "rgba(255, 255, 255, 0.22)" : "rgba(0, 0, 0, 0.25)";

        layout = layout || {};
        layout.paper_bgcolor = "rgba(0,0,0,0)";
        layout.plot_bgcolor = "rgba(0,0,0,0)";
        layout.font = Object.assign(layout.font || {}, {
            family: "Schibsted Grotesk, sans-serif",
            color: fontColor
        });

        ["xaxis", "yaxis", "xaxis2", "yaxis2", "scene"].forEach((axisKey) => {
            if (layout[axisKey]) {
                if (axisKey === "scene") {
                    ["xaxis", "yaxis", "zaxis"].forEach((subKey) => {
                        if (layout.scene[subKey]) {
                            layout.scene[subKey].gridcolor = gridColor;
                            layout.scene[subKey].color = fontColor;
                        }
                    });
                } else {
                    layout[axisKey].gridcolor = gridColor;
                    layout[axisKey].zerolinecolor = zeroLineColor;
                    layout[axisKey].color = fontColor;
                }
            }
        });

        return layout;
    }
    

    window.renderPlot = function (containerId, figure) {
        const container = document.getElementById(containerId);
        if (!container || !figure) return;

        const layout = applyThemeToLayout(figure.layout || {});
        const config = {
            responsive: true,
            displayModeBar: true,
            displaylogo: false,
            modeBarButtonsToRemove: ["toImage"],
            scrollZoom: true
        };

        Plotly.react(container, figure.data || [], layout, config);
        container._axionFigure = figure;
    };

    

    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === "data-theme") {
                document.querySelectorAll(".graph-viewport").forEach((container) => {
                    if (container._axionFigure && window.Plotly) {
                        const updatedLayout = applyThemeToLayout(container._axionFigure.layout);
                        Plotly.relayout(container, updatedLayout);
                    }
                });
            }
        });
    });
    observer.observe(document.documentElement, { attributes: true });

    // export helpers
    window.downloadBlob = function (content, filename, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

})();
