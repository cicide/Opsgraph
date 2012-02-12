// import Nevow.Athena

LoadSuites = {};

LoadSuites.LoadSuiteWidget = Nevow.Athena.Widget.subclass('LoadSuites.LoadSuiteWidget');

LoadSuites.LoadSuiteWidget.methods(

    function __init__(self, node) {
        LoadSuites.LoadSuiteWidget.upcall(self, '__init__', node);
        window.onload = self.initialize();
    },
    
    function initialize(self) {
        // use a deferred passed back from the server to get the row data
        var theTablerows = self.callRemote('initialize').addCallback(
            function(result) {
                if (result) {
                    self.addSuiteListings(result);
                }
            }
        );
        
    },
    
    function addSuiteListings (self, row_array) {
        // get a nonConflict jquery handle
        var $jq = jQuery.noConflict();
        var tbo = document.getElementById('loadSuitesTableBody');
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
            var insertPos = insertIndex + i;
            var newRow = tbo.insertRow(insertPos);
            newRow.setAttribute('id', 'dbId'+row_id);
            var nameCell = newRow.insertCell(0);
            nameCell.align ='center';
            var tmp = document.createTextNode(row_name);
            nameCell.appendChild(tmp);
            var descCell = newRow.insertCell(1);
            descCell.align ='center';
            var tmp = document.createTextNode(row_desc);
            descCell.appendChild(tmp);
            var authCell = newRow.insertCell(2);
            authCell.align ='center';
            var tmp = document.createTextNode(row_auth);
            authCell.appendChild(tmp);
            var birthCell = newRow.insertCell(3);
            birthCell.align ='center';
            var tmp = document.createTextNode(row_birth);
            birthCell.appendChild(tmp);
            var actionCell = newRow.insertCell(4);
            actionCell.align ='center';
            var tmp1 = document.createElement('a');
            tmp1.setAttribute('href', '#');
            var tmp1icon = document.createElement('img');
            tmp1icon.setAttribute('src', 'images/edit_16.gif');
            tmp1.appendChild(tmp1icon);
            tmp1.onclick = (function(value) {
                return function(){
                    self.onEditSuite(value);
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
                    self.onViewSuite(value);
                }
            })(row_id);
            actionCell.appendChild(tmp1);
            actionCell.appendChild(tmp2);
            actionCell.appendChild(tmp3);
        }
        $jq('.sortableTable').dataTable();
    },
    
    function onEditSuite(self, dbId) {
        url = self.callRemote('editSuite', dbId).addCallback(
            function (result) {
                if (result) {
                    window.location = result;
                } else {
                    // display error modal here
                }
                return false;
            }
        );
    },
    
    function onViewSuite(self, dbId) {
        var $jq = jQuery.noConflict();
        var vWidth = $jq(window).width();
        var vHeight = $jq(window).height();
        self.callRemote('viewSuite', dbId);
        window.open('createSuite?sid='+dbId+'&perms=ro','vSuite'+dbId,'status=0,toolbar=0,scrollbars=0,menubar=0,location=0,directories=0,resizable=1,width='+vWidth+',height='+vHeight);
        return false;
    },
    
    function reDirect(self, url) {
        window.location = url;
        return true;
    }
);