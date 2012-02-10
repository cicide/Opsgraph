// import Nevow.Athena

LoadGraphs = {};

LoadGraphs.LoadGraphWidget = Nevow.Athena.Widget.subclass('LoadGraphs.LoadGraphWidget');

LoadGraphs.LoadGraphWidget.methods(
    function __init__(self, node) {
        LoadGraphs.LoadGraphWidget.upcall(self, '__init__', node);
        window.onload = self.initialize();
    },
    
    function initialize(self) {
        self.callRemote('initialize');
    },
    
    function addGraphListings (self, row_array) {
        // get a nonConflict jquery handle
        var $jq = jQuery.noConflict();
        var tbo = document.getElementById('loadGraphsTableBody');
        // get insert start position
        var tboRowCount = tbo.rows.length;
        var insertIndex = tboRowCount;
        var newRowCount = row_array.length;
        for (var i=0; i<newRowCount; i++) {
            var row_data = row_array[i];
            var row_id = row_data[0];
            var row_name = row_data[1];
            var row_desc = row_data[2];
            var row_auth = row_data[3];
            var row_birth = row_data[4];
            var row_eng = row_data[5];
            var row_type = row_data[6];
            var insertPos = insertIndex + i;
            var newRow = tbo.insertRow(insertPos);
            newRow.setAttribute('id', 'grDbId'+row_id);
            var checkBoxCell = newRow.insertCell(0);
            checkBoxCell.align ='center';
            var tmp = document.createElement('input');
            tmp.setAttribute('type', 'checkbox');
            tmp.setAttribute('name', 'actionBox');
            tmp.setAttribute('value', row_id);
            checkBoxCell.appendChild(tmp);
            var nameCell = newRow.insertCell(1);
            nameCell.align ='center';
            var tmp = document.createTextNode(row_name);
            nameCell.appendChild(tmp);
            var descCell = newRow.insertCell(2);
            descCell.align ='center';
            var tmp = document.createTextNode(row_desc);
            descCell.appendChild(tmp);
            var authCell = newRow.insertCell(3);
            authCell.align ='center';
            var tmp = document.createTextNode(row_auth);
            authCell.appendChild(tmp);
            var birthCell = newRow.insertCell(4);
            birthCell.align ='center';
            var tmp = document.createTextNode(row_birth);
            birthCell.appendChild(tmp);
            var engineCell = newRow.insertCell(5);
            engineCell.align ='center';
            var tmp = document.createTextNode(row_eng);
            engineCell.appendChild(tmp);
            var typeCell = newRow.insertCell(6);
            typeCell.align ='center';
            var tmp = document.createTextNode(row_type);
            typeCell.appendChild(tmp);
            var actionCell = newRow.insertCell(7);
            actionCell.align ='center';
            var tmp1 = document.createElement('a');
            tmp1.setAttribute('href', '#');
            var tmp1icon = document.createElement('img');
            tmp1icon.setAttribute('src', 'images/edit_16.gif');
            tmp1.appendChild(tmp1icon);
            tmp1.onclick = (function(value) {
                return function(){
                    self.onEditGraph(value);
                }
            })(row_id);
            var tmp2 = document.createTextNode(' ');
            var tmp3 = document.createElement('a');
            tmp3.setAttribute('href', '#');
            var tmp3icon = document.createElement('img');
            tmp3icon.setAttribute('src', 'images/view_16.gif');
            tmp3.appendChild(tmp3icon);
            tmp3.onclick = (function(value) {
                return function(){
                    self.onViewGraph(value);
                }
            })(row_id);
            actionCell.appendChild(tmp1);
            actionCell.appendChild(tmp2);
            actionCell.appendChild(tmp3);
        }
        if (insertIndex == 0) {
            // this table is new, create the select all checkbox, and add the form submit buttons
            var selectAll = document.createElement('input');
            selectAll.setAttribute('type', 'checkbox');
            var selectAllCell = document.getElementById('all_toggle');
            // var thisForm = document.getElementById('loadGraphForm');
            selectAll.onclick = function () {self.onSelectAllToggle('loadGraphForm', 'actionBox', this.checked)};
            // var theOldCell = selectAllCell.childnodes[0];
            // selectAllCell.replaceChild(selectAll, theOldCell);
            selectAllCell.appendChild(selectAll);
            // make the button row
            var theButtonRow = document.getElementById('form_button_row');
            var theForm = document.getElementById('loadGraphForm');
            var theDeleteButton = document.createElement('input');
            theDeleteButton.setAttribute('type','button');
            theDeleteButton.setAttribute('name', 'Delete Selection');
            theDeleteButton.setAttribute('value', 'Delete Selection');
            theDeleteButton.onclick = function () { self.onDeleteSelection('loadGraphForm', 'actionBox'); }
            theButtonRow.appendChild(theDeleteButton);
            var theCreateSuiteButton = document.createElement('input');
            theCreateSuiteButton.setAttribute('type', 'button');
            theCreateSuiteButton.setAttribute('name', 'Create Graph Suite');
            theCreateSuiteButton.setAttribute('value', 'Create Graph Suite');
            theCreateSuiteButton.onclick = function() { self.onCreateSuite('loadGraphForm', 'actionBox'); }
            theButtonRow.appendChild(theCreateSuiteButton);
        }
        $jq('.sortableTable').dataTable();
    },
    
    function onEditGraph(self, grDbId) {
        url = self.callRemote('editGraph', grDbId);
        //window.location = url;
        return false;
    },
    
    function onViewGraph(self, grDbId) {
        self.callRemote('viewGraph', grDbId);
        window.open('viewGraph?cid='+grDbId,'vGraph'+grDbId,'status=0,toolbar=0,scrollbars=0,menubar=0,location=0,directories=0,resizable=1,width=600,height=400');
        return false;
    },
    
    function reDirect(self, url) {
        window.location = url;
    },
    
    function onCreateSuite(self, formName, fieldName) {
        if (!document.forms[formName]) {
            return false;
        }
        var objCheckBoxes = document.forms[formName].elements[fieldName];
        if (!objCheckBoxes) {
            return false;
        }
        var countCheckBoxes = objCheckBoxes.length;
        if (!countCheckBoxes) {
            return false;
        } else {
            var checkedBoxes = []
            for (var i=0; i<countCheckBoxes; i++) {
                if (objCheckBoxes[i].checked) {
                    checkedBoxes.push(objCheckBoxes[i].value);
                }
            }
            self.callRemote('createSuite', checkedBoxes).addCallback(
                function (result) {
                    if (result) {
                        self.reDirect(result);
                    }
                }
            );
            return false;
        }
    },
    
    function onDeleteSelection(self, formName, fieldName) {
        if (!document.forms[formName]) {
            return false;
        }
        var objCheckBoxes = document.forms[formName].elements[fieldName];
        if (!objCheckBoxes) {
            return false;
        }
        var countCheckBoxes = objCheckBoxes.length;
        if (!countCheckBoxes) {
            return false;
        } else {
            var checkedBoxes = []
            for (var i=0; i<countCheckBoxes; i++) {
                if (objCheckBoxes[i].checked) {
                    checkedBoxes.push(objCheckBoxes[i].value);
                }
            }
            self.callRemote('deleteGraphs', checkedBoxes).addCallback(
                function (result) {
                    if (result) {
                        var $jq = jQuery.noConflict();
                        var theSortableTable = $jq('.sortableTable').dataTable();
                        for (var i=0; i<result.length; i++) {
                            var theDeleteRow = document.getElementById('grDbId'+result[i]);
                            theSortableTable.fnDeleteRow(theDeleteRow);
                        }
                    }
                    return false;
                }
            );
            return false;
        }
        
    },
    
    function onSelectAllToggle(self, formName, fieldName, isChecked) {
        if (!document.forms[formName]) {
            return false;
        }
        var objCheckBoxes = document.forms[formName].elements[fieldName];
        if (!objCheckBoxes) {
            return false;
        }
        var countCheckBoxes = objCheckBoxes.length;
        if (!countCheckBoxes) {
            objCheckBoxes.checked = isChecked;
        } else {
            for (var i=0; i<countCheckBoxes; i++) {
                objCheckBoxes[i].checked = isChecked;
            }
        }
    }
);