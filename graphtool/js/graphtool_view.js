// import Nevow.Athena

ViewGraphs = {};

ViewGraphs.ViewGraphWidget = Nevow.Athena.Widget.subclass('ViewGraphs.ViewGraphWidget');

ViewGraphs.ViewGraphWidget.methods(

    function __init__(self, node) {
        ViewGraphs.ViewGraphWidget.upcall(self, '__init__', node);
        window.onload = self.initialize();
    },
    
    function initialize(self) {
        self.callRemote('initialize');
    },
    
    function addFusionChart(self, chartType, chartId, chartWidth, chartHeight, chart_data) {
        var theGraphCell = document.getElementById('graphArea');
        var newChart = new FusionCharts("fusioncharts/"+chartType, chartId, chartWidth, chartHeight, "0", "1");
        newChart.setJSONData(chart_data);
        newChart.render('graphArea');
    },
    
    function addHighChart(self, chart_object) {
        var high_chart = new Object();
        //var chart_options = chart_object['plotOptions'];
        var chart_series = chart_object['series'];
        var chart_chart = chart_object['chart'];
        var chart_yAxis = chart_object['yAxis'];
        var chart_xAxis = chart_object['xAxis'];
        var chart_title = chart_object['title'];
        var series_count = chart_series.length;
        var series_array = [];
        // convert any plotBands start and end times to integers
        var chart_plotBands = chart_xAxis['plotBands'];
        var plotBands_count = chart_plotBands.length;
        var band_array = [];
        if (plotBands_count) {
            for (var i=0; i<plotBands_count; i++) {
                var fmt_band = new Object();
                // convert color to rgb
                var band_hex_color = chart_plotBands[i]['color'];
                var band_r_color = parseInt(band_hex_color.substring(0,2),16);
                var band_g_color = parseInt(band_hex_color.substring(2,4),16);
                var band_b_color = parseInt(band_hex_color.substring(4,6),16);
                var band_alpha = parseInt(chart_plotBands[i]['alpha']);
                fmt_band.color = 'rgba('+band_r_color+', '+band_g_color+', '+band_b_color+', 0.'+band_alpha+')';
                fmt_band.from = parseInt(chart_plotBands[i]['from'])*1000;
                fmt_band.to = parseInt(chart_plotBands[i]['to'])*1000;
                fmt_band.label = chart_plotBands[i]['label'];
                //alert('band color: '+ fmt_band.color + ' from: '+ fmt_band.from + ' to: ' + fmt_band.to + ' label: ' + fmt_band.label);
                band_array.push(fmt_band);
            }
        }
        chart_xAxis['plotBands'] = band_array;
        // reset the height and width to 100% of the view window
        // we should do this in the server with some kind of height override
        var chart_newChart = new Object();
        render_to = chart_chart['renderTo'];
        var hostCell = document.getElementById(render_to);
        alert('graph render to is '+render_to);
        chart_type = chart_chart['type'];
        chart_zoomType = chart_chart['zoomType'];
        chart_newChart['renderTo'] = render_to;
        chart_newChart['type'] = chart_type;
        chart_newChart['zoomType'] = chart_zoomType;
        // convert the unicodeized strings to ints and floats for series
        for (var i=0; i<series_count; i++) {
            var series_name = chart_series[i]['name'];
            var series_data = chart_series[i]['data'];
            var series_data_count = series_data.length;
            var series_fmt_data = [];
            for (var j=0; j<series_data_count; j++) {
                var x_val = parseInt(series_data[j][0])*1000;
                var y_val = parseFloat(series_data[j][1]);
                var x_y = [x_val, y_val];
                series_fmt_data.push(x_y);
            }
            var fmt_series = new Object();
            fmt_series.name = series_name;
            fmt_series.data = series_fmt_data;
            series_array.push(fmt_series);
        }
        var chart_options = { line: { lineWidth: 1,
                                      marker: { enabled: false,
                                                states: { hover: { enabled: true,
                                                                   radius: 5
                                                                 }
                                                        }
                                              },
                                      states: { hover: { lineWidth: 3 
                                                       }
                                              },
                                      shadow: false
                                    },
                              area: { lineWidth: 1,
                                      marker: { enabled: false,
                                                states: { hover: { enabled: true,
                                                                   radius: 5
                                                                 }
                                                        }
                                              },
                                      states: { hover: { lineWidth: 3
                                                       }
                                              },
                                      shadow: false
                                    }
                            };
        // build the new chart object
        high_chart.chart = chart_newChart;
        high_chart.plotOptions = chart_options;
        high_chart.yAxis = chart_yAxis;
        high_chart.xAxis = chart_xAxis;
        high_chart.title = chart_title;
        high_chart.series = series_array;
        var chart = new Highcharts.Chart(high_chart);
        hostCell.onresize = function () {self.onHCCellResize(chart, hostCell);};
    },
    
    function onHCCellResize(self, highChart, hostCell) {
        var $jq = jQuery.noConflict();
        var theHeight = $jq(hostCell).height();
        var theWidth = $jq(hostCell).width();
        alert('resizing to '+theWidth+' x '+theHeight);
        highChart.setSize(theWidth,theHeight)
        highChart.redraw();
    },
    
    function reDirect(self, url) {
        window.location = url;
        return true;
    }
);