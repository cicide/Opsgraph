// import Nevow.Athena

ViewSuites = {};

ViewSuites.ViewSuiteWidget = Nevow.Athena.Widget.subclass('ViewSuites.ViewSuiteWidget');

var charts = {}  //global chart tracker

ViewSuites.ViewSuiteWidget.methods(

    function __init__(self, node) {
        ViewSuites.ViewSuiteWidget.upcall(self, '__init__', node);
        window.onload = self.initialize();
        self.highCharts = [];
    },
    
    function initialize(self) {
        result = self.callRemote('initialize').addCallback(
            function(result) {
                if (result) {
                    theModalAutoClose = result[7];
                    self.createSortableList(result[0], result[1], result[2], result[3], result[4], result[5], result[6]);
                } else {
                    // display an error here
                    return false;
                }
            }
        );
    },
    
    function createSelect(self, name, id, def_option, options) {
        var theSelect = document.createElement('select');
        theSelect.name = name;
        theSelect.setAttribute('id', id);
        var i=0
        if (def_option.length > 0) {
            var def_opt = def_option[0];
            var def_val = def_option[1];
            var theOption = document.createElement('option');
            var cont = document.createTextNode(def_opt);
            cont.value = def_val;
            theOption.appendChild(cont);
            theSelect.appendChild(theOption);
        }
        for (i=0; i<options.length; i++) {
            if (options[i] != def_opt) {
                var theOption = document.createElement('option');
                var cont = document.createTextNode(options[i]);
                theOption.appendChild(cont);
            }
            if (i == 0) {
                theOption.selected;
            }
            theSelect.appendChild(theOption);
        }
        theSelect.onchange = function() {self.onChangeSelect(theSelect)};
        return theSelect
    },
    
    function addNamedTextInput(self, field_cell, text_name, field_name, default_value, specials) {
    // this add a text input field with a preceding name
    var theFieldCell = document.getElementById(field_cell);
    var theTextInput = document.createElement('input');
    theTextInput.setAttribute('type', 'text');
    theTextInput.name = field_name;
    theTextInput.setAttribute('id', field_name);
    theTextInput.defaultValue = default_value;
    theTextInput.onchange = function () {self.onChangeText(theTextInput)};
    var tmp = document.createTextNode(text_name);
    var theWholeField = document.createElement('div');
    theWholeField.appendChild(tmp);
    theWholeField.appendChild(theTextInput);
    if (specials == 'datetime') {
        var $jq = jQuery.noConflict();
        var theTextIdField = field_name+'pick';
        theTextInput.setAttribute('id', theTextIdField);
        var theTimeNow = new Date();
        theTextInput.onclick = function() {
            $jq("#"+theTextIdField).datetimepicker(
                {
                }
            );
        };
        var datetime_link = document.createElement('a');
        var cal_image = document.createElement('img');
        cal_image.setAttribute('src', 'images/cal.gif');
        cal_image.setAttribute('width', '16');
        cal_image.setAttribute('height', '16');
        cal_image.setAttribute('border', '0');
        cal_image.setAttribute('alt', 'Pick a date');
        theWholeField.appendChild(datetime_link);
        $jq(theWholeField).find("#"+theTextIdField).datetimepicker( { });
    }
    theFieldCell.appendChild(theWholeField);
    return false;
    },
    
    function createSortableList(self, id_array, parentDiv, suiteName, suiteTitle, suiteTime, suiteDur, suiteCols) {
        var theParentDiv = document.getElementById(parentDiv);
        var theList = document.createElement('ul');
        theList.setAttribute('class', 'suiteSortable3');
        theList.setAttribute('id', 'suiteSortable');
        var idCount = id_array.length;
        for (var i=0; i<idCount; i++) {
            var tmpDiv = document.createElement('div');
            tmpDiv.setAttribute('id', 'gid'+ id_array[i]);
            tmpDiv.setAttribute('class', 'graphDiv');
            tmpText = document.createTextNode(id_array[i]);
            tmpDiv.appendChild(tmpText);
            var litem = document.createElement('li');
            litem.setAttribute('class', 'ui-state-default');
            litem.setAttribute('id', id_array[i]);
            litem.appendChild(tmpDiv);
            theList.appendChild(litem);
        }
        theParentDiv.appendChild(theList);
        $jq = jQuery.noConflict();
        $jq("#suiteSortable").sortable({placeholder: 'ui-state-highlight'});
        $jq("#suiteSortable").disableSelection();
        // add the control bar
        var theControlBar = document.getElementById('suiteControl');
        theControlBar.style.display = 'none';
        var theControlBarTable = document.createElement('table');
        theControlBarTable.setAttribute('width', '100%');
        var theSaveRow = document.createElement('tr');
        var theSaveCol1 = document.createElement('td');
        theSaveCol1.setAttribute('id', 'save1');
        var theSaveCol2 = document.createElement('td');
        theSaveCol2.setAttribute('id', 'save2');
        var theSaveCol3 = document.createElement('td');
        theSaveCol3.setAttribute('id', 'save3');
        var theSaveCol4 = document.createElement('td');
        theSaveCol4.setAttribute('id', 'save4');
        theSaveRow.appendChild(theSaveCol1);
        theSaveRow.appendChild(theSaveCol2);
        theSaveRow.appendChild(theSaveCol3);
        theSaveRow.appendChild(theSaveCol4);
        var theOverrideRow = document.createElement('tr');
        var theOverrideCol1 = document.createElement('td');
        theOverrideCol1.setAttribute('id', 'over1');
        var theOverrideCol2 = document.createElement('td');
        theOverrideCol2.setAttribute('id', 'over2');
        var theOverrideCol3 = document.createElement('td');
        theOverrideCol3.setAttribute('id', 'over3');
        var theOverrideCol4 = document.createElement('td');
        theOverrideCol4.setAttribute('id', 'over4');
        theOverrideRow.appendChild(theOverrideCol1);
        theOverrideRow.appendChild(theOverrideCol2);
        theOverrideRow.appendChild(theOverrideCol3);
        theOverrideRow.appendChild(theOverrideCol4);
        theControlBar.appendChild(theControlBarTable);
        theControlBarTable.appendChild(theSaveRow);
        theControlBarTable.appendChild(theOverrideRow);
        var theColumnSelect = document.createElement('select');
        theColumnSelect.name = 'columnSelect';
        theColumnSelect.setAttribute('id', 'columnSelect');
        theColumnSelect.onchange = function () {self.onChangeSelect(theColumnSelect)};
        var optionOne = document.createElement('option');
        var tmp = document.createTextNode('1');
        optionOne.value='1';
        optionOne.appendChild(tmp);
        theColumnSelect.appendChild(optionOne);
        var optionTwo = document.createElement('option');
        var tmp = document.createTextNode('2');
        optionTwo.value='2';
        optionTwo.appendChild(tmp);
        theColumnSelect.appendChild(optionTwo);
        var optionThree = document.createElement('option');
        var tmp = document.createTextNode('3');
        optionThree.value='3';
        optionThree.appendChild(tmp);
        // optionThree.selected;
        theColumnSelect.appendChild(optionThree);
        var optionFour = document.createElement('option');
        var tmp = document.createTextNode('4');
        optionFour.value='4';
        optionFour.appendChild(tmp);
        theColumnSelect.appendChild(optionFour);
        var optionFive = document.createElement('option');
        var tmp = document.createTextNode('5');
        optionFive.value='5';
        optionFive.appendChild(tmp);
        theColumnSelect.appendChild(optionFive);
        var selectArray = [ optionOne, optionTwo, optionThree, optionFour, optionFive ];
        var theArrayPointer = parseInt(suiteCols) - 1;
        var theSelectedArray = selectArray[theArrayPointer];
        theSelectedArray.selected;
        theColumnSelect.selectedIndex = theArrayPointer;
        var theColumnSelectName = document.createTextNode('Columns: ');
        theSaveCol1.appendChild(theColumnSelectName);
        theSaveCol1.appendChild(theColumnSelect);
        var theLockButton = document.createElement('input');
        theLockButton.setAttribute('type', 'button');
        theLockButton.setAttribute('name', 'Lock Positions');
        theLockButton.setAttribute('value', 'Lock Positions');
        theLockButton.setAttribute('id', 'lockButton');
        theLockButton.onclick = function () {self.toggleLock()};
        theSaveCol1.appendChild(theLockButton);
        var theSaveButton = document.createElement('input');
        theSaveButton.setAttribute('type', 'button');
        theSaveButton.setAttribute('name', 'Save');
        theSaveButton.setAttribute('value', 'Save');
        theSaveButton.onclick = function () {self.onSaveSuite("#suiteSortable")};
        theSaveCol4.appendChild(theSaveButton);
        theSaveCol4.setAttribute('align', 'right');
        self.addNamedTextInput('save2', 'Suite Name: ', 'suiteName', suiteName, false);
        self.addNamedTextInput('save3', 'Suite Description: ', 'suiteDesc', suiteTitle, false);
        self.addNamedTextInput('over2', 'Start Time: ', 'startTime', suiteTime, 'datetime');
        self.addNamedTextInput('over3', 'Duration: ', 'suiteDuration', suiteDur, false);
        var theApplyButton = document.createElement('input');
        theApplyButton.setAttribute('id', 'applyOverrideButton');
        theApplyButton.setAttribute('type', 'button');
        theApplyButton.setAttribute('name', 'Apply');
        theApplyButton.setAttribute('value', 'Apply');
        theApplyButton.onclick = function () {self.onApplyOverrides()};
        theOverrideCol4.appendChild(theApplyButton);
        theOverrideCol4.setAttribute('align', 'right');
        // initialize the column select value
        self.onChangeSelect(theColumnSelect);
        self.callRemote('tableLoadComplete');
    },
    
    function onSaveSuite(self, suite_id) {
        var $jq = jQuery.noConflict();
        var theModalDiv = document.getElementById('saveDialog');
        if (theModalDiv != null) {
            // reset the modal div's content
            var theOldText = theModalDiv.firstChild;
            var theNewText = document.createTextNode('Saving...');
            theModalDiv.replaceChild(theNewText, theOldText);
        } else {
            var theParentModalDiv = document.createElement('div');
            var theModalDiv = document.createElement('div');
            theModalDiv.setAttribute('id', 'saveDialog');
            theModalDiv.setAttribute('title', 'Saving the Suite');
            var theModalDivText = document.createTextNode('Saving...');
            theModalDiv.appendChild(theModalDivText);
            theParentModalDiv.style.display = 'none';
            theParentModalDiv.appendChild(theModalDiv);
            var theBody = document.getElementsByTagName('body')[0];
            theBody.appendChild(theParentModalDiv);
        }
        var list_array = $jq(suite_id).sortable("toArray");
        $jq("#saveDialog").dialog({ modal: true, close: function (event, ui) {$jq(this).dialog("destroy");} });
        var result = self.callRemote('saveSuite', list_array).addCallback(
            function (result) {
                if (result) {
                    if (theModalAutoClose) {
                        $jq("#saveDialog").dialog("close");
                    } else {
                        var theModalDiv = document.getElementById('saveDialog');
                        var theOldText = theModalDiv.firstChild;
                        var theModalDivText = document.createTextNode('Save Complete!');
                        theModalDiv.replaceChild(theModalDivText, theOldText);
                        $jq("#saveDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                    }
                    // note save successful and remove saving overlay
                } else {
                    // not save failure and display error/remove overlay
                    var theModalDiv = document.getElementById('saveDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Save Failed');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#saveDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                }
            }
        );
    },
    
    function onApplyOverrides(self) {
        var $jq = jQuery.noConflict();
        var theModalDiv = document.getElementById('applyDialog');
        if (theModalDiv != null) {
            // reset the modal div's content
            var theOldText = theModalDiv.firstChild;
            var theNewText = document.createTextNode('Applying Override Settings...');
            theModalDiv.replaceChild(theNewText, theOldText);
        } else {
            var theParentModalDiv = document.createElement('div');
            var theModalDiv = document.createElement('div');
            theModalDiv.setAttribute('id', 'applyDialog');
            theModalDiv.setAttribute('title', 'Applying Override Settings');
            var theModalDivText = document.createTextNode('Applying Override Settings...');
            theModalDiv.appendChild(theModalDivText);
            theParentModalDiv.style.display = 'none';
            theParentModalDiv.appendChild(theModalDiv);
            var theBody = document.getElementsByTagName('body')[0];
            theBody.appendChild(theParentModalDiv);
        }
        $jq("#applyDialog").dialog({ modal: true, close: function (event, ui) {$jq(this).dialog("destroy");}});
        var result = self.callRemote('applyOverrides').addCallback(
            function (result) {
                if (result) {
                    var theModalDiv = document.getElementById('applyDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Apply Complete!');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#applyDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                } else {
                    var theModalDiv = document.getElementById('applyDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Apply Failed.');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#applyDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                }
            }
        );
    },
    
    function toggleLock(self) {
        var $jq = jQuery.noConflict();
        var theLockButton = document.getElementById('lockButton');
        if (theLockButton.value == 'Lock Positions') {
            $jq("#suiteSortable").sortable("disable");
            theLockButton.setAttribute('name', 'Unlock Positions');
            theLockButton.setAttribute('value', 'Unlock Positions');
        } else {
            $jq("#suiteSortable").sortable("enable");
            theLockButton.setAttribute('name', 'Lock Positions');
            theLockButton.setAttribute('value', 'Lock Positions');
        }
        return false;
    },
    
    function lockPositions(self) {
        var $jq = jQuery.noConflict();
        var theLockButton = document.getElementById('lockButton');
        if (theLockButton.value == 'Lock Positions'){
            $jq("#suiteSortable").sortable("disable");
            theLockButton.setAttribute('name', 'Unlock Positions');
            theLockButton.setAttribute('value', 'Unlock Positions');
        }
    },
    
    function addFusionChart(self, div_id, chartType, chartId, chartWidth, chartHeight, chart_data, chart_cell) {
        var theGraphCell = document.getElementById(div_id);
        var newChart = new FusionCharts("fusioncharts/"+chartType, chartId, chartWidth, chartHeight, "0", "1");
        theGraphCell.onresize = function () {self.onChartResize(theGraphCell, newChart);};
        newChart.setJSONData(chart_data);
        newChart.render(div_id);
    },
    
    function addHighChart(self, chart_object, list_id, defChart) {
        var theListElement = document.getElementById(list_id);
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
        var theGraphCell = document.getElementById(render_to);
        chart_type = chart_chart['type'];
        chart_zoomType = chart_chart['zoomType'];
        chart_newChart['renderTo'] = render_to;
        chart_newChart['type'] = chart_type;
        chart_newChart['zoomType'] = chart_zoomType;
        // convert the unicodeized strings to ints and floats for series
        for (var i=0; i<series_count; i++) {
            var series_name = chart_series[i]['name'];
            var series_id = chart_series[i]['seriesId'];
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
            fmt_series.id = series_id;
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
        charts[defChart] = chart;
        theListElement.onresize = function () {self.onChartResize(theListElement, chart);};
        self.highCharts.push(chart);
    },
    
    function addPoint(self, chartId, seriesId, dataPoint) {
        var theChart = charts[chartId];
        var theSeries = theChart.get(seriesId);
        var x_data = dataPoint[0];
        var y_data = dataPoint[1];
        var x_val = parseInt(x_data)*1000;
        var y_val = parseFloat(y_data);
        var x_y = [x_val, y_val];
        theSeries.addPoint(x_y, true, true);
        return false;
    },
    
    function onChangeText(self, theText) {
        var tmp = theText.value;
        var tmp2 = theText.name;
        self.callRemote('setItem', tmp2, tmp);
        // nothing here
        return false;
    },
    
    function onChangeSelect(self, theSelected) {
        var selIndex = theSelected.selectedIndex;
        var theValue = theSelected.options[selIndex].value;
        var theSelectedName = theSelected.name;
        self.callRemote('setItem', 'numCols', theValue);
        $jq = jQuery.noConflict()
        if (theSelectedName == 'columnSelect') {
            var theOldClass = document.getElementById('suiteSortable').className;
            if (theValue == '1') {
                if (theOldClass == 'suiteSortable1') {
                    return false;
                } else {
                    $jq('#suiteSortable').removeClass(theOldClass).addClass('suiteSortable1');
                }
            } else if (theValue == '2') {
                if (theOldClass == 'suiteSortable2') {
                    return false;
                } else {
                    $jq('#suiteSortable').removeClass(theOldClass).addClass('suiteSortable2');
                }
            } else if (theValue =='3') {
                if (theOldClass == 'suiteSortable3') {
                    return false;
                } else {
                    $jq('#suiteSortable').removeClass(theOldClass).addClass('suiteSortable3');
                }
            } else if (theValue == '4') {
                if (theOldClass == 'suiteSortable4') {
                    return false;
                } else {
                    $jq('#suiteSortable').removeClass(theOldClass).addClass('suiteSortable4');
                }
            } else if (theValue == '5') {
                if (theOldClass == 'suiteSortable5') {
                    return false;
                } else {
                    $jq('#suiteSortable').removeClass(theOldClass).addClass('suiteSortable5');
                }
            }
            var highCharts_count = self.highCharts.length;
            for (var i=0; i<highCharts_count; i++) {
                var $jq = jQuery.noConflict();
                var chart = self.highCharts[i];
                var div_id = chart.container;
                var theContainer = div_id.parentNode.parentNode;
                alert('chart container: '+theContainer);
                var theHeight = $jq(theContainer).height();
                var theWidth = $jq(theContainer).width();
                var width = div_id.offsetWidth;
                var height = div_id.offsetHeight;
                alert('setting width and height to: '+ theWidth +' x '+ theHeight);
                chart.setSize( theWidth, theHeight, false);
            }
            return false;
        }
    },
    
    function hideItem(self, item) {
        var theItem = document.getElementById(item);
        theItem.style.display = 'none';
        return false;
    },
    
    function unhideItem(self, item) {
        var theItem = document.getElementById(item);
        theItem.style.display = '';
    },
    
    function displayError(self, error_msg, error_element) {
        // display error message and put red border around cell
        var $jq = jQuery.noConflict();
        $jq('#'+error_element).addClass('input-error');
        return false;
    },
    
    function clearError(self, error_msg, error_element) {
        var $jq = jQuery.noConflict();
        $jq('#'+error_element).removeClass('input-error');
        return false;
    },
    
    function onChartResize(self, cell, chart) {
        alert('resize called on '+cell);
    },
    
    function reDirect(self, url) {
        window.location = url;
        return true;
    }
);
