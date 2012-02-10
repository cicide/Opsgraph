// import Nevow.Athena

Extern = {};

Extern.ExternWidget = Nevow.Athena.Widget.subclass('Extern.ExternWidget');

Extern.ExternWidget.methods(
    function __init__(self, node) {
        Extern.ExternWidget.upcall(self, '__init__', node);
        window.onload = self.initialize();
    },
    
    function initialize(self) {
    var tmp = self.createTable('select_table');
    self.callRemote('initialize');
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

    function createSettingsRow(self, row_id) {
        var theSettingsRow = document.createElement('tr');
        var the1SettingsCell = document.createElement('td');
        the1SettingsCell.setAttribute('id', row_id + '1SettingsCell');
        the1SettingsCell.setAttribute('width', '20%');
        the1SettingsCell.style.display = 'none';
        the1SettingsCellContent = document.createElement('div');
        the1SettingsCellContent.setAttribute('id', row_id + '1SettingsCellContent');
        the1SettingsCell.appendChild(the1SettingsCellContent);
        var the2SettingsCell = document.createElement('td');
        the2SettingsCell.setAttribute('id', row_id + '2SettingsCell');
        the2SettingsCell.setAttribute('width', '20%');
        the2SettingsCell.style.display = 'none';
        the2SettingsCellContent = document.createElement('div');
        the2SettingsCellContent.setAttribute('id', row_id + '2SettingsCellContent');
        the2SettingsCell.appendChild(the2SettingsCellContent);
        var the3SettingsCell = document.createElement('td');
        the3SettingsCell.setAttribute('id', row_id + '3SettingsCell');
        the3SettingsCell.setAttribute('width', '20%');
        the3SettingsCell.style.display = 'none';
        the3SettingsCellContent = document.createElement('div');
        the3SettingsCellContent.setAttribute('id', row_id + '3SettingsCellContent');
        the3SettingsCell.appendChild(the3SettingsCellContent);
        var the4SettingsCell = document.createElement('td');
        the4SettingsCell.setAttribute('id', row_id + '4SettingsCell');
        the4SettingsCell.setAttribute('width', '20%');
        the4SettingsCell.style.display = 'none';
        the4SettingsCellContent = document.createElement('div');
        the4SettingsCellContent.setAttribute('id', row_id + '4SettingsCellContent');
        the4SettingsCell.appendChild(the4SettingsCellContent);
        var the5SettingsCell = document.createElement('td');
        the5SettingsCell.setAttribute('id', row_id + '5SettingsCell');
        the5SettingsCell.setAttribute('width', '10%');
        the5SettingsCell.style.display = 'none';
        the5SettingsCellContent = document.createElement('div');
        the5SettingsCellContent.setAttribute('id', row_id + '5SettingsCellContent');
        the5SettingsCell.appendChild(the5SettingsCellContent);
        var the6SettingsCell = document.createElement('td');
        the6SettingsCell.setAttribute('id', row_id + '6SettingsCell');
        the6SettingsCell.setAttribute('width', '10%');
        the6SettingsCell.style.display = 'none';
        the6SettingsCellContent = document.createElement('div');
        the6SettingsCellContent.setAttribute('id', row_id + '6SettingsCellContent');
        the6SettingsCell.appendChild(the6SettingsCellContent);
        theSettingsRow.appendChild(the1SettingsCell);
        theSettingsRow.appendChild(the2SettingsCell);
        theSettingsRow.appendChild(the3SettingsCell);
        theSettingsRow.appendChild(the4SettingsCell);
        theSettingsRow.appendChild(the5SettingsCell);
        theSettingsRow.appendChild(the6SettingsCell);
        return theSettingsRow;
    },
    
    function createGraphSettings(self) {
        // create a table for the graph settings form
        var theSettingsTable = document.createElement('table');
        theSettingsTable.setAttribute('id', 'settingsTable');
        theSettingsTable.setAttribute('width', '100%');
        var theFirstSettingsRow = self.createSettingsRow('1');
        theFirstSettingsRow.setAttribute('id', 'firstSettingsRow');
        var theSecondSettingsRow = self.createSettingsRow('2');
        theSecondSettingsRow.setAttribute('id', 'secondSettingsRow');
        //theSecondSettingsRow.style.display = 'none';
        var theThirdSettingsRow = self.createSettingsRow('3');
        theThirdSettingsRow.setAttribute('id', 'thirdSettingsRow');
        //theThirdSettingsRow.style.display = 'none';
        var theFourthSettingsRow = self.createSettingsRow('4');
        theFourthSettingsRow.setAttribute('id', 'fourthSettingsRow');
        //theFourthSettingsRow.style.display = 'none';
        var theFifthSettingsRow = self.createSettingsRow('5');
        theFifthSettingsRow.setAttribute('id', 'fifthSettingsRow');
        //theFifthSettingsRow.style.display = 'none';
        var theCreateButtonRow = document.createElement('tr');
        var theCreateButtonCell = document.createElement('td');
        theCreateButtonCell.setAttribute('id', 'makeGraphButtonCell');
        theCreateButtonCell.setAttribute('colspan', '6');
        theCreateButtonCell.setAttribute('align', 'right');
        theCreateButtonRow.setAttribute('id', 'makeGraphButtonRow');
        theCreateButtonRow.style.display = '';
        theCreateButtonRow.appendChild(theCreateButtonCell);
        // build the make graph button
        var theMakeGraphButton = document.createElement('input');
        theMakeGraphButton.setAttribute('type', 'button');
        theMakeGraphButton.setAttribute('value', 'Generate Graph');
        theMakeGraphButton.onclick = function () {self.generateGraph()};
        // add the button to it's cell
        theCreateButtonCell.appendChild(theMakeGraphButton);
        theSettingsTable.appendChild(theFirstSettingsRow);
        theSettingsTable.appendChild(theSecondSettingsRow);
        theSettingsTable.appendChild(theThirdSettingsRow);
        theSettingsTable.appendChild(theFourthSettingsRow);
        theSettingsTable.appendChild(theFifthSettingsRow);
        theSettingsTable.appendChild(theCreateButtonRow);
        self.callRemote('getOptions', 'setting_options');
        return theSettingsTable;
    },
    
    function createTable(self, sectionId) {
        var theSection = document.body;
        //var theSection = document.getElementById(sectionId);
        // build the select table
        var selectTable = document.createElement('table');
        selectTable.setAttribute('id', 'selectTable');
        // create the table head with the table column names shown
        var tbh = document.createElement('thead');
        var theHeaderRow = document.createElement('tr');
        // Node column
        var theHeaderNodeCell = document.createElement('td');
        theHeaderNodeCell.setAttribute('width', '10%');
        var temp = document.createTextNode('Node');
        theHeaderNodeCell.appendChild(temp);
        theHeaderRow.appendChild(theHeaderNodeCell);
        // Host column
        var theHeaderHostCell = document.createElement('td');
        theHeaderHostCell.setAttribute('width', '40%');
        var temp = document.createTextNode('Host');
        theHeaderHostCell.appendChild(temp);
        theHeaderRow.appendChild(theHeaderHostCell);
        // Service column
        var theHeaderServiceCell = document.createElement('td');
        theHeaderServiceCell.setAttribute('width', '20%');
        var temp = document.createTextNode('Service');
        theHeaderServiceCell.appendChild(temp);
        theHeaderRow.appendChild(theHeaderServiceCell);
        // Metric column
        var theHeaderMetricCell = document.createElement('td');
        theHeaderMetricCell.setAttribute('width', '20%');
        var temp = document.createTextNode('Metric');
        theHeaderMetricCell.appendChild(temp);
        theHeaderRow.appendChild(theHeaderMetricCell);
        // Action column
        var theHeaderActionCell = document.createElement('td');
        theHeaderActionCell.setAttribute('width', '10%');
        var temp = document.createTextNode('Action');
        theHeaderActionCell.appendChild(temp);
        theHeaderRow.appendChild(theHeaderActionCell);
        tbh.appendChild(theHeaderRow);
        // create the table body
        var tbo = document.createElement('tbody');
        tbo.setAttribute('id', 'graphSelectTableBody');
        // create the input form
        var theForm = document.createElement('form');
        theForm.setAttribute('id', 'graphSelectForm');
        theForm.onSubmit = function() {self.onMetricSelect(this)};
        // the top rows should be data rows from previously entered series
        // create the input row
        var theSeriesSelectRow = document.createElement('tr');
        // create the node select cell
        var theNodeSelectCell = document.createElement('td');
        var tmp = new Array();
        var theNodeSelect = self.createSelect('node', 'node_options', tmp, tmp);
        theNodeSelectCell.appendChild(theNodeSelect);
        theNodeSelectCell.setAttribute('id', 'node_select_cell');
        theSeriesSelectRow.appendChild(theNodeSelectCell);
        // create the host select cell and hide it
        var theHostSelectCell = document.createElement('td');
        var tmp = new Array();
        var theHostSelect = self.createSelect('host', 'host_options', tmp, tmp);
        theHostSelectCell.appendChild(theHostSelect);
        theHostSelectCell.setAttribute('id', 'host_select_cell');
        theHostSelectCell.style.display = 'none';
        theSeriesSelectRow.appendChild(theHostSelectCell);
        // create the service select cell and hide it
        var theServiceSelectCell = document.createElement('td');
        var tmp = new Array();
        var theServiceSelect = self.createSelect('service', 'service_options', tmp, tmp);
        theServiceSelectCell.appendChild(theServiceSelect);
        theServiceSelectCell.setAttribute('id', 'service_select_cell');
        theServiceSelectCell.style.display = 'none';
        theSeriesSelectRow.appendChild(theServiceSelectCell);
        // create the metric select cell and hide it
        var theMetricSelectCell = document.createElement('td');
        var tmp = new Array();
        var theMetricSelect = self.createSelect('metric', 'metric_options', tmp, tmp);
        theMetricSelectCell.appendChild(theMetricSelect);
        theMetricSelectCell.setAttribute('id', 'metric_select_cell');
        theMetricSelectCell.style.display = 'none';
        theSeriesSelectRow.appendChild(theMetricSelectCell);
        // create the action cell and hide it
        var theActionCell = document.createElement('td');
        var theActionCellSubmit = document.createElement('input');
        theActionCellSubmit.setAttribute('type', 'button');
        // theActionCellSubmit.setAttribute('name', 'Add to Graph');
        theActionCellSubmit.setAttribute('value', 'Add to Graph');
        theActionCellSubmit.onclick = function() {self.onMetricSelect()};
        theActionCell.appendChild(theActionCellSubmit);
        theActionCell.setAttribute('id', 'submit_cell');
        theActionCell.style.display = 'none';
        theSeriesSelectRow.appendChild(theActionCell);
        tbo.appendChild(theSeriesSelectRow);
        // put together the table
        selectTable.appendChild(tbh);
        selectTable.appendChild(tbo);
        theForm.appendChild(selectTable);
        // theSection.appendChild(theForm);
        // create the big table
        var theBigTable = document.createElement('table');
        theBigTable.setAttribute('width', '100%');
        theBigTable.setAttribute('id', 'main_display_table');
        // create the table rows
        var theBigSeriesRow = document.createElement('tr');
        var theFirstSeparatorRow = document.createElement('tr');
        var theBigMakeGraphRow = document.createElement('tr');
        var theSecondSeparatorRow = document.createElement('tr');
        var theBigGraphRow = document.createElement('tr');
        // add the rows to the table in order
        theBigTable.appendChild(theBigSeriesRow);
        theBigTable.appendChild(theFirstSeparatorRow);
        theBigTable.appendChild(theBigMakeGraphRow);
        theBigTable.appendChild(theSecondSeparatorRow);
        theBigTable.appendChild(theBigGraphRow);
        // create the separator cells and add them to the separator rows
        var theFirstSeparatorCell = document.createElement('td');
        var theSecondSeparatorCell = document.createElement('td');
        var theFirstSeparator = document.createElement('hr');
        var theSecondSeparator = document.createElement('hr');
        theFirstSeparatorCell.setAttribute('colspan', '5');
        theSecondSeparatorCell.setAttribute('colspan', '5');
        theFirstSeparatorCell.appendChild(theFirstSeparator);
        theSecondSeparatorCell.appendChild(theSecondSeparator);
        theFirstSeparatorRow.appendChild(theFirstSeparatorCell);
        theSecondSeparatorRow.appendChild(theSecondSeparatorCell);
        // create the series selection cell and insert the series form
        var theBigSeriesCell = document.createElement('td');
        theBigSeriesCell.setAttribute('width', '100%');
        theBigSeriesCell.appendChild(theForm);
        // add the series cell to the series row
        theBigSeriesRow.appendChild(theBigSeriesCell);
        // create the cell for the graph settings and make graph button
        var theBigMakeGraphCell = document.createElement('td');
        theBigMakeGraphCell.setAttribute('colspan', '5');
        var theBigMakeGraphCellContents = self.createGraphSettings();
        theBigMakeGraphCell.appendChild(theBigMakeGraphCellContents);
        // put graph settings cell in the graph settings row
        theBigMakeGraphRow.appendChild(theBigMakeGraphCell);
        // create the main graph cell
        var theBigGraphCell = document.createElement('td');
        theBigGraphCell.setAttribute('id', 'chart_cell');
        // add the main graph cell to it's row
        theBigGraphRow.appendChild(theBigGraphCell);
        // add the save graph button 
        var theSaveGraphButtonRow = document.createElement('tr');
        theSaveGraphButtonRow.setAttribute('id', 'saveGraphButtonRow');
        theSaveGraphButtonRow.style.display = 'none';
        var theSaveGraphButtonCell = document.createElement('td');
        theSaveGraphButtonCell.setAttribute('align', 'right');
        var theSaveGraphButton = document.createElement('input');
        theSaveGraphButton.setAttribute('type', 'button');
        theSaveGraphButton.setAttribute('value', 'Save Graph');
        theSaveGraphButton.onclick = function () {self.saveGraph()};
        theSaveGraphButtonCell.appendChild(theSaveGraphButton);
        theSaveGraphButtonRow.appendChild(theSaveGraphButtonCell);
        theBigTable.appendChild(theSaveGraphButtonRow);
        // add the big table to the body of the page
        theSection.appendChild(theBigTable);
        self.callRemote('getOptions', 'node_options');
    },

    function onMetricSelect(self) {
        self.callRemote('addServiceMetric', 'submit');
        return false;
    },
    
    function generateGraph(self) {
        //self.callRemote('makeGraph');
        //return false;
        var $jq = jQuery.noConflict();
        var theModalDiv = document.getElementById('generateDialog');
        if (theModalDiv != null) {
            // reset the modal div's content
            var theOldText = theModalDiv.firstChild;
            var theNewText = document.createTextNode('Generating Graph...');
            theModalDiv.replaceChild(theNewText, theOldText);
        } else {
            var theParentModalDiv = document.createElement('div');
            var theModalDiv = document.createElement('div');
            theModalDiv.setAttribute('id', 'generateDialog');
            theModalDiv.setAttribute('title', 'Generating the Graph');
            var theModalDivText = document.createTextNode('Generating...');
            theModalDiv.appendChild(theModalDivText);
            theParentModalDiv.style.display = 'none';
            theParentModalDiv.appendChild(theModalDiv);
            var theBody = document.getElementsByTagName('body')[0];
            theBody.appendChild(theParentModalDiv);
        }
        var list_array = $jq('#generateDialog').sortable("toArray");
        $jq("#generateDialog").dialog({ modal: true,
                                        close: function (event, ui) {$jq(this).dialog("destroy");} });
        var result = self.callRemote('makeGraph').addCallback(
            function (result) {
                if (result) {
                    var theModalDiv = document.getElementById('generateDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Graph Generation Complete!');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#generateDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                    // note generate successful and remove saving overlay
                } else {
                    // note generate failure and display error/remove overlay
                    var theModalDiv = document.getElementById('generateDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Graph Generation Failed');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#generateDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
                }
            }
        );
        return false;
    },

    function saveGraph(self) {
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
            theModalDiv.setAttribute('title', 'Saving the Graph');
            var theModalDivText = document.createTextNode('Saving...');
            theModalDiv.appendChild(theModalDivText);
            theParentModalDiv.style.display = 'none';
            theParentModalDiv.appendChild(theModalDiv);
            var theBody = document.getElementsByTagName('body')[0];
            theBody.appendChild(theParentModalDiv);
        }
        var list_array = $jq('#saveDialog').sortable("toArray");
        $jq("#saveDialog").dialog({ 
            modal: true,
            close: function (event, ui) {$jq(this).dialog("destroy");}
        });
        var result = self.callRemote('saveGraph').addCallback(
            function (result) {
                if (result) {
                    var theModalDiv = document.getElementById('saveDialog');
                    var theOldText = theModalDiv.firstChild;
                    var theModalDivText = document.createTextNode('Save Complete!');
                    theModalDiv.replaceChild(theModalDivText, theOldText);
                    $jq("#saveDialog").dialog( "option", "buttons", { "Ok": function() { $jq(this).dialog("close");}});
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
        return false;
    },
    
    function addSelect(self, optionList, optionListId, selectId, def_option) {
        var theOldSelect = document.getElementById(optionListId);
        var theSelectCell = theOldSelect.parentNode;
        var theSelect = self.createSelect(selectId, optionListId, def_option, optionList);
        theSelectCell.replaceChild(theSelect, theOldSelect);
        theSelectCell.style.display = '';
        if (optionListId == 'host_options') {
            var theHostSelectCell = document.getElementById('host_select_cell');
            theHostSelectCell.style.display = '';
            var theServiceSelectCell = document.getElementById('service_select_cell');
            theServiceSelectCell.style.display = 'none';
            var theMetricSelectCell = document.getElementById('metric_select_cell');
            theMetricSelectCell.style.display = 'none';
            var theSubmitCell = document.getElementById('submit_cell');
            theSubmitCell.style.display = 'none';
        } else if (optionListId == 'node_options') {
            var theHostSelectCell = document.getElementById('host_select_cell');
            theHostSelectCell.style.display = 'none';
            var theServiceSelectCell = document.getElementById('service_select_cell');
            theServiceSelectCell.style.display = 'none';
            var theMetricSelectCell = document.getElementById('metric_select_cell');
            theMetricSelectCell.style.display = 'none';
            var theSubmitCell = document.getElementById('submit_cell');
            theSubmitCell.style.display = 'none';
        } else if (optionListId == 'service_options') {
            var theServiceSelectCell = document.getElementById('service_select_cell');
            theServiceSelectCell.style.display = '';
            var theMetricSelectCell = document.getElementById('metric_select_cell');
            theMetricSelectCell.style.display = 'none';
            var theSubmitCell = document.getElementById('submit_cell');
            theSubmitCell.style.display = 'none';
        } else if (optionListId == 'metric_options') {
            var theMetricSelectCell = document.getElementById('metric_select_cell');
            theMetricSelectCell.style.display = '';
            var theSubmitCell = document.getElementById('submit_cell');
            theSubmitCell.style.display = 'none';
        }
    },

    function addNamedSelect(self, optionList, optionListId, selectId, def_option, select_name) {
    // this adds a select with a preceding name (defined in select_name)
    var theOldSelect = document.getElementById(optionListId);
    var theSelectListId = optionListId + 'Select';
    var theSelectCell = theOldSelect.parentNode;
    var theSelect = self.createSelect(selectId, theSelectListId, def_option, optionList);
    var tmp = document.createTextNode(select_name);
    var theWholeField = document.createElement('div');
    theWholeField.setAttribute('id', optionListId);
    theWholeField.appendChild(tmp);
    theWholeField.appendChild(theSelect);
    theSelectCell.replaceChild(theWholeField, theOldSelect);
    theSelectCell.style.display = '';
    },
    
    function addNamedTextInput(self, field_id, text_name, field_name, default_value, specials) {
    // this add a text input field with a preceding name
    var theOldField = document.getElementById(field_id);
    var theFieldCell = theOldField.parentNode;
    var theTextInput = document.createElement('input');
    theTextInput.setAttribute('type', 'text');
    theTextInput.name = field_name;
    theTextInput.setAttribute('id', field_name);
    theTextInput.defaultValue = default_value;
    theTextInput.onchange = function () {self.onChangeText(theTextInput)};
    var tmp = document.createTextNode(text_name);
    var theWholeField = document.createElement('div');
    theWholeField.setAttribute('id', field_id);
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
        $jq(theWholeField).find("#"+theTextIdField).datetimepicker(
                                                            {maxDate: new Date(),
                                                             stepMinute: 5,
                                                             showButtonPanel: true,
                                                             });
    }
    theFieldCell.replaceChild(theWholeField, theOldField);
    return false;
    },

    function addGraphSeries(self, node, host, service, metric, row_id) {
        var tbo = document.getElementById('graphSelectTableBody');
        var tboRowCount = tbo.rows.length;
        var insertIndex = tboRowCount - 1;
        var row = tbo.insertRow(insertIndex);
        row.setAttribute('id', 'seriesId'+row_id);
        var nodeCell = row.insertCell(0);
        var tmp = document.createTextNode(node);
        nodeCell.appendChild(tmp);
        var hostCell = row.insertCell(1);
        var tmp = document.createTextNode(host);
        hostCell.appendChild(tmp);
        var serviceCell = row.insertCell(2);
        var tmp = document.createTextNode(service);
        serviceCell.appendChild(tmp);
        var metricCell = row.insertCell(3);
        var tmp = document.createTextNode(metric);
        metricCell.appendChild(tmp);
        var actionCell = row.insertCell(4);
        var tmp = document.createElement('input');
        tmp.setAttribute('type', 'button');
        tmp.setAttribute('value', 'Remove');
        tmp.onclick = function () {self.onRowRemove(row)};
        actionCell.appendChild(tmp);
    },
    
    function addFusionChart(self, chartType, chartId, chartWidth, chartHeight, chart_data, chart_cell) {
        var theGraphCell = document.getElementById(chart_cell);
        var newChart = new FusionCharts("fusioncharts/"+chartType, chartId, chartWidth, chartHeight, "0", "1");
        newChart.setJSONData(chart_data);
        newChart.render(chart_cell);
        var theSaveGraphButtonRow = document.getElementById('saveGraphButtonRow');
        theSaveGraphButtonRow.style.display = '';
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
        // set the chart options
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
        high_chart.chart = chart_chart;
        high_chart.plotOptions = chart_options;
        high_chart.yAxis = chart_yAxis;
        high_chart.xAxis = chart_xAxis;
        high_chart.title = chart_title;
        high_chart.series = series_array;
        var chart = new Highcharts.Chart(high_chart);
        var theSaveGraphButtonRow = document.getElementById('saveGraphButtonRow');
        theSaveGraphButtonRow.style.display = '';
    },
    
    function onRowRemove(self, theRow) {
        var theRowId = theRow.getAttribute('id');
        self.callRemote('removeRowId', theRowId)
        return false;
    },
    
    function removeRow(self, theRowId) {
        var theRow = document.getElementById(theRowId);
        var theRowIndex = theRow.rowIndex - 1; //remove the head row from the count
        var theTable = theRow.parentNode;
        theTable.deleteRow(theRowIndex);
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
        var theSelectName = theSelected.name;
        
        if (theSelectName == 'node') {
            // the node select item has changed
            if (theValue == 'Select a Node') {
                // don't do anything at all if somehow they have selected 'select a node' option
                return false;
            } else {
                // Remove the select node option if it's value is 'select_an_option'
                if (theSelected.options[0].value == 'Select a Node') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'node', theValue);
            return false;
        } else if (theSelectName == 'host') {
            if (theValue == 'Select a Host') {
                // don't do anything at all if somehow they have selected the 'select an option' option
                return false
            } else { 
                //Remove the select host option if it's value is 'select_an_option' (index 0)
                if (theSelected.options[0].value == 'Select a Host') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'host', theValue);
        } else if (theSelectName == 'service') {
            if (theValue == 'Select a Service') {
                // don't do anything at all if somehow they have selected the 'select an option' option
                return false
            } else { 
                //Remove the select service option if it's value is 'select_an_option' (index 0)
                if (theSelected.options[0].value == 'Select a Service') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'service', theValue);
        }  else if (theSelectName == 'metric') {
            if (theValue == 'Select a Metric') {
                // don't do anything at all if somehow they have selected the 'select an option' option
                return false
            } else { 
                //Remove the select metric option if it's value is 'select_an_option' (index 0)
                if (theSelected.options[0].value == 'Select a Metric') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'metric', theValue);
            var theSubmitCell = document.getElementById('submit_cell');
            theSubmitCell.style.display = '';
        } else if (theSelectName == 'engine') {
            if (theValue == 'Select a Graphing Engine') {
                // don't do anything at all if somehow they have selected the 'select and option option'
                return false
            } else {
                // remove the select engine option it it's value is 'select_an_option' (index 0)
                if (theSelected.options[0].value == 'Select a Graphing Engine') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'engine', theValue);
        } else if (theSelectName == 'graphtype') {
            if (theValue == 'Select a Graph Type') {
                // don't do anything at all if somehow they have selected the 'select and option option'
                return false
            } else {
                // remove the select engine option it it's value is 'select_an_option' (index 0)
                if (theSelected.options[0].value == 'Select a Graph Type') {
                    theSelected.remove(0);
                }
            }
            self.callRemote('setItem', 'graphtype', theValue);
        } else if (theSelectName == 'graph_size') {
            self.callRemote('setItem', theSelectName, theValue);
        } else if (theSelectName == 'event_type') {
            self.callRemote('setItem', theSelectName, theValue);
        } else {
            // Catch all for unknown select name
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
    }
);