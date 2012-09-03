import utils
from nevow import url
from formless import annotate
from formless import webform
from nevow import loaders
from nevow import rend
from nevow import tags as T
from nevow import inevow
from nevow import livepage
from twisted.internet import defer
from opsview import node_list as allowed_node_list
import subscriber

log = utils.get_logger(__name__)

class RegisterPage(rend.Page):
    """ Register a new user Page"""
    
    def __init__(self):
        rend.Page.__init__(self)
        self.remember(self, inevow.ICanHandleNotFound)
    
    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''

    def _renderErrors(self, ctx, data):
        log.debug("RegisterForm: _renderErrors called")
        log.debug('RegisterForm: context: %s' % ctx)
        log.debug('RegisterForm: data: %s' % data)
        request = inevow.IRequest(ctx)
        #log.debug('RegisterForm:: %s' % str(request.args))
        if 'register-failure' in request.args:
            registerError = 'Invalid Registration'
        else:
            registerError = ''
        return registerError

    def data_opsviewnodes(self, ctx, data):
        log.debug("RegisterForm: opsview nodes - %s"%str(allowed_node_list))
        return allowed_node_list

    def render_opsviewnodes(self, ctx, opsviewnodes):
        ctx_tag = ctx.tag
        for node in allowed_node_list.keys():
            ctx_tag.children.append(T.tr[T.td(colspan='2')[' ']])
            ctx_tag.children.append(T.tr[T.td(colspan='2')[T.hr]])
            ctx_tag.children.append(T.tr[T.td['Login ID (%s):'%node], T.td[T.input(type='text', name='login_%s'%node)]]) 
            ctx_tag.children.append(T.tr[T.td['Password (%s):'%node], T.td[T.input(type='password', name='pass_%s'%node)]]) 
            
        log.debug("RegisterForm:ctx_tag=%s"%str(ctx_tag))
        return ctx_tag
    
    def child_register_user(self, ctx):
        log.debug("RegisterForm: register_user() called")
        args = inevow.IRequest(ctx).args
        #log.debug("RegisterForm: args = %s"%str(args))
        errors = [] 
        opsview_creds = []
        # 1. Do some form validation here
        for field_name, field_value in args.iteritems():
            if field_name == 'username':
                if field_value[0] == None or len(field_value[0]) == 0:
                    errors.append("Login ID: Please enter a valid email id.")
                elif not utils.is_valid_email(field_value[0]):
                    errors.append("Login ID: Please enter a valid email id.")
                elif subscriber.isDuplicate(field_value[0]):
                    errors.append("Login ID: This login id is already taken.")
            elif field_name == 'password':
                if field_value[0] == None or len(field_value[0]) == 0:
                    errors.append("Pasword: Please enter a valid password.")
                elif len(field_value[0]) < 6:
                    errors.append("Password: Length should be atleast 6 characters long.")
            elif field_name == 'cpassword':
                if field_value[0] == None or len(field_value[0]) == 0 or field_value[0] != args['password'][0]:
                    errors.append("Confirm Pasword: Please reenter the same password.")
            elif "login_" in field_name:
                if field_value[0] == None or len(field_value[0]) == 0:
                    errors.append("Login ID (%s): Please enter a valid login id."%field_name.split('_')[1])
                else:
                    cred = {}
                    cred["server_name"] = field_name.split('_')[1]
                    cred["login_id"]    = field_value[0]
                    cred["password"]    = args['pass_%s'%field_name.split('_')[1]][0]
                    opsview_creds.append(cred) 
            elif "pass_" in field_name:
                if field_value[0] == None or len(field_value[0]) == 0:
                    errors.append("Password (%s): Please enter a valid password."%field_name.split('_')[1])
        if len(errors) > 0:
            # Need to push errors bac to form
            pass
        else:         
            # 2. create the subscriber
            #log.debug("RegisterForm: Got opsview_creds = %s"%opsview_creds)
            d = subscriber.createSubscriber(username = args['username'][0],
                                            password = args['password'][0],
                                            first_name = args['firstname'][0],
                                            last_name = args['lastname'][0],
                                            opsview_creds = opsview_creds)
            return d
        return None

    ######################### Generate the page ######################
    addSlash = True
    docFactory = loaders.stan(
        T.html[
            T.head[
                T.title["Opsgraph: Please Register"],
                T.style(type="text/css")[
                    T.comment[""" #outer {
                                  position: absolute;
                                  top: 50%;
                                  left: 0px;
                                  width: 100%;
                                  height: 1px;
                                  overflow: visible;
                                  }

                                  #inner {
                                  width: 400px;
                                  height: 300px;
                                  margin-left: -200;  /***  width / 2   ***/
                                  position: absolute;
                                  top: -150px;          /***  height / 2   ***/
                                  left: 50%;
                                  }
                                  
                                  .registerErr {text-align: center; color: red; font-weight: bold}
                                  .input-error {border:2px solid red;}"""
                    ]
                ]
            ],
            T.body[
                T.div(id='outer')[
                    T.div(id='inner')[
                        T.form(action="register_user", method="POST")[
                            T.table[
                                T.tr[
                                    T.td(class_='registerErr', colspan='2') [_renderErrors]
                                ],
                                T.tr[
                                    T.td[ "Login ID (Email):" ],
                                    T.td[ T.input(type='text', name='username') ],
                                ],
                                T.tr[
                                    T.td[ "Password:" ],
                                    T.td[ T.input(type='password', name='password') ],
                                ],
                                T.tr[
                                    T.td[ "Confirm Password:" ],
                                    T.td[ T.input(type='password', name='cpassword') ],
                                ],
                                T.tr[
                                    T.td[ "First Name:" ],
                                    T.td[ T.input(type='text', name='firstname') ],
                                ],
                                T.tr[
                                    T.td[ "Last Name:" ],
                                    T.td[ T.input(type='text', name='lastname') ],
                                ],
                                T.p(render=T.directive('opsviewnodes'), data=T.directive('opsviewnodes')),
                                T.tr[
                                    T.td(align='right', colspan='2')[" "]
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[" "]
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[
                                        T.input(type='submit', value='register')
                                    ]
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[" "]
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[" "]
                                ],
                                T.tr[
                                    T.td(align='right', colspan='2')[T.a(href='/')['Back to login']]
                                ],
                            ],
                        ]
                    ]
                ]
            ]
        ])


######################################################################################

class RegisterForm (livepage.LivePage):
    ''' Register a new user in the system '''

    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Please Register'

    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''

    def _generate_formtag():
        ''' Generate the html for the form tag '''

        value_list = ["document.getElementById('opsview_fields').value", "document.getElementById('username').value", "document.getElementById('password').value", "document.getElementById('cpassword').value", "document.getElementById('fname').value", "document.getElementById('lname').value"]

        opsview_field_list = []
        for node in allowed_node_list.keys():
            value_list.append("document.getElementById('login_%s').value"%node)
            value_list.append("document.getElementById('pass_%s').value"%node)
            opsview_field_list.append("login_%s"%node)
            opsview_field_list.append("pass_%s"%node)

        form_tag = '''<form method="POST" name="registeruser" id="registeruser" onsubmit="server.handle('processregister', %s); return false;"><input type="hidden" name="opsview_fields" id="opsview_fields" value="%s" />''' %((', '.join(x for x in value_list)), ('|'.join(x for x in opsview_field_list)) )

        #log.debug("RegisterForm: form tag = %s"%form_tag)

        return form_tag
    
    def _generate_opsview_fields():
        ''' Generate html for the opsview credentials input fields'''
        value_list = []
        for node in allowed_node_list.keys():
            value_list.append("<tr><td colspan='2'> </td></tr>")
            value_list.append("<tr><td colspan='2'><hr /></td></tr>")
            value_list.append("<tr><td>Login ID (%s):</td><td><input type='text' id='login_%s' name='login_%s' /></td></tr>"%(node, node, node))
            value_list.append("<tr><td>Password (%s):</td><td><input type='password' id='pass_%s' name='pass_%s' /></td></tr>"%(node, node, node))
        opsview_tag = "%s" %(''.join(x for x in value_list))

        #log.debug("RegisterForm: opsview tag = %s"%opsview_tag)

        return opsview_tag

    def handle_processregister(self, ctx, *args):
        #log.debug("RegisterForm: processregister() called - args=%s"%str(args))

        def onSuccess(result):
            log.debug("RegisterForm: onSuccess: result = %s"%str(result))
            client.sendScript(livepage.js('resetForm')())
            yield livepage.set('err_msg', ''), livepage.eol
            yield livepage.set('success_msg', 'Congratulations. Your have registered successfully'), livepage.eol

        def onFailure(failure):
            log.debug("RegisterForm: onFailure: result = %s"%str(failure))
            errmsg = ''
            try:
                errmsg = failure.getErrorMessage() or ''
            except:
                pass
            yield livepage.set('success_msg', ''), livepage.eol
            yield livepage.set('err_msg', 'Sorry, the registration process was not successful. %s'%errmsg), livepage.eol

        req_args = inevow.IRequest(ctx).args
        client = livepage.IClientHandle(ctx)
        #log.debug("RegisterForm: processregister() called - Request args=%s"%str(args))

        # form validation
        if not args or len(args) < 6:
            yield livepage.set('err_msg', 'Please fill all the fields in the form'), livepage.eol
        else:
            opsview_field_names = args[0]
            opsview_field_names = opsview_field_names.split('|')
            opsview_dic = {}
            opsview_creds = []
            username  = args[1] 
            npassword = args[2] 
            cpassword = args[3] 
            fname     = args[4] 
            lname     = args[5] 
            opsview_values = args[6:]
            if not username or len(username) < 1:
                yield livepage.set('err_msg', 'Please enter your graphtool login id.'), livepage.eol
            elif not npassword or len(npassword) < 1:
                yield livepage.set('err_msg', 'Please enter the new password you want to set!'), livepage.eol
            elif npassword != cpassword:
                yield livepage.set('err_msg', 'The New Password and Confirm Password do not match!'), livepage.eol
            elif not fname or len(fname) < 1:
                yield livepage.set('err_msg', 'Please enter your first name.'), livepage.eol
            elif not lname or len(lname) < 1:
                yield livepage.set('err_msg', 'Please enter your last name.'), livepage.eol
            else:
                opsview_dic = dict(zip(opsview_field_names, opsview_values))
                #log.debug("RegisterForm: processregister: opsview_dic=%s"%opsview_dic)    

                for field in opsview_field_names:
                    if field.startswith("login_"):
                        opsview_cred = {}
                        opsview_cred["server_name"] = field.split('_')[1]
                        opsview_cred["login_id"]    = opsview_dic[field]
                        opsview_creds.append(opsview_cred)
                for cred in opsview_creds:
                    cred["password"] = opsview_dic["pass_%s"%cred["server_name"]]
                #log.debug("RegisterForm: opsview_creds=%s"%opsview_creds)

                # Register now
                d = subscriber.createSubscriber(username      = username,
                                                password      = npassword,
                                                first_name    = fname,
                                                last_name     = lname,
                                                opsview_creds = opsview_creds)
                d.addCallback(onSuccess) 
                d.addErrback(onFailure) 

                yield d
    
    ######################## Create Page ###########################

    PAGE_STRING = '''
           <html xmlns:nevow="http://nevow.com/ns/nevow/0.1">
           <title>Opsgraph: Please Register</title>
           <head>
                <nevow:invisible nevow:render="liveglue"/>
                <style type="text/css" >
                    #outer {
                         position: absolute;
                          top: 50%%;
                          left: 0px;
                          width: 100%%;
                          height: 1px;
                          overflow: visible;
                          }

                      #inner {
                          width: 400px;
                          height: 300px;
                          margin-left: -200;  /***  width / 2   ***/
                          position: absolute;
                          top: -150px;          /***  height / 2   ***/
                          left: 50%%;
                          }
                      .success_msg {text-align: center; color: green; font-weight: bold}
                      .err_msg {text-align: center; color: red; font-weight: bold}
                </style> 
                <script>
                    function resetForm(){
                        document.getElementById("registeruser").reset();
                    }
                </script>
           </head>
           <body>
             <div id="outer">
              <div id="inner">
              <div id="success_msg" class="success_msg"></div>
              <div id="err_msg" class="err_msg"></div>
                  %s
                  <table>
                    <tr><td>Login ID:</td><td><input type="text" id="username" name="username" /></td></tr>
                    <tr><td>Password:</td><td><input type="password" id="password" name="password" /></td></tr>
                    <tr><td>Confirm Password:</td><td><input type="password" id="cpassword" name="cpassword" /></td></tr>
                    <tr><td>First Name:</td><td><input type="fname" id="fname" name="fname" /></td></tr>
                    <tr><td>Last Name:</td><td><input type="lname" id="lname" name="lname" /></td></tr>
                    %s
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"><button type="submit">Register</button></td></tr>
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"><a href="/">Back to login</a></td></tr>
                 </table>
              </form>
           </div>
         </div></body></html>
    '''%(_generate_formtag(), _generate_opsview_fields())

    #print PAGE_STRING

    docFactory = loaders.xmlstr(PAGE_STRING)


######################################################################################

class ChangePasswordForm (livepage.LivePage):

    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Change Password'

    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''

    def _generate_formtag():
        ''' <form onsubmit="server.handle('processchange',document.getElementById('cpassword').value,document.getElementById('password').value); return false;" method="POST" name="changepass"> '''

        value_list = ["document.getElementById('opsview_fields').value", "document.getElementById('username').value", "document.getElementById('password').value", "document.getElementById('npassword').value", "document.getElementById('cpassword').value"]

        opsview_field_list = []
        for node in allowed_node_list.keys():
            value_list.append("document.getElementById('login_%s').value"%node)
            value_list.append("document.getElementById('pass_%s').value"%node)
            opsview_field_list.append("login_%s"%node)
            opsview_field_list.append("pass_%s"%node)

        form_tag = '''<form method="POST" name="changepass" id="changepass" onsubmit="server.handle('processchange', %s); return false;"><input type="hidden" name="opsview_fields" id="opsview_fields" value="%s" />''' %((', '.join(x for x in value_list)), ('|'.join(x for x in opsview_field_list)) )

        #log.debug("ChangePasswordForm: form tag = %s"%form_tag)

        return form_tag
    
    def _generate_opsview_fields():
        ''' 
            <p> <tr><td colspan="2"> </td></tr>
            <tr><td colspan="2"><hr /></td></tr>
            <tr><td>Login ID (netgeeks):</td><td><input type="text" id="login_netgeeks" name="login_netgeeks" /></td></tr>
            <tr><td>Password (netgeeks):</td><td><input type="password" id="pass_netgeeks" name="pass_netgeeks" /></td></tr>
            <tr><td colspan="2"> </td></tr>
            <tr><td colspan="2"><hr /></td></tr>
            <tr><td>Login ID (kixeye):</td><td><input type="text" id="login_kixeye" name="login_kixeye" /></td></tr>
            <tr><td>Password (kixeye):</td><td><input type="password" id="pass_kixeye" name="pass_kixeye" /></td></tr></p>
        '''
        value_list = []
        for node in allowed_node_list.keys():
            value_list.append("<tr><td colspan='2'> </td></tr>")
            value_list.append("<tr><td colspan='2'><hr /></td></tr>")
            value_list.append("<tr><td>Login ID (%s):</td><td><input type='text' id='login_%s' name='login_%s' /></td></tr>"%(node, node, node))
            value_list.append("<tr><td>Password (%s):</td><td><input type='password' id='pass_%s' name='pass_%s' /></td></tr>"%(node, node, node))
        opsview_tag = "%s" %(''.join(x for x in value_list))

        #log.debug("ChangePasswordForm: opsview tag = %s"%opsview_tag)

        return opsview_tag

    def child_changepassword(self, ctx):
        log.debug("ChangePasswordForm: child_changepassword() called")
        args = inevow.IRequest(ctx).args
        #log.debug("ChangePasswordForm: args = %s"%str(args))
        client = livepage.IClientHandle(ctx)
        yield livepage.set('responsestr', 'Hello Dolly!'), livepage.eol

    def handle_processchange(self, ctx, *args):
        #log.debug("ChangePasswordForm: processchange() called - args=%s"%str(args))

        def onSuccess(result):
            log.debug("ChangePasswordForm: onSuccess: result = %s"%str(result))
            client.sendScript(livepage.js('resetForm')())
            yield livepage.set('err_msg', ''), livepage.eol
            yield livepage.set('success_msg', 'Your password was succesfully changed!'), livepage.eol

        def onFailure(failure):
            log.debug("ChangePasswordForm: onFailure: result = %s"%str(failure))
            errmsg = ''
            try:
                errmsg = failure.getErrorMessage() or ''
            except:
                pass
            yield livepage.set('success_msg', ''), livepage.eol
            yield livepage.set('err_msg', 'Sorry, your password change was not successful. %s'%errmsg), livepage.eol

        req_args = inevow.IRequest(ctx).args
        client = livepage.IClientHandle(ctx)
        #log.debug("ChangePasswordForm: PROCESS CHANGE() called - Request args=%s"%str(args))

        # form validation
        if not args or len(args) < 5:
            yield livepage.set('err_msg', 'Please fill all the fields in the form'), livepage.eol
        else:
            opsview_field_names = args[0]
            opsview_field_names = opsview_field_names.split('|')
            opsview_dic = {}
            opsview_creds = []
            username  = args[1] 
            tpassword = args[2] 
            npassword = args[3] 
            cpassword = args[4] 
            opsview_values = args[5:]
            if not username or len(username) < 1:
                yield livepage.set('err_msg', 'Please enter your graphtool login id.'), livepage.eol
            elif not tpassword or len(tpassword) < 1:
                yield livepage.set('err_msg', 'Please enter your current or temporary password!'), livepage.eol
            elif not npassword or len(npassword) < 6:
                yield livepage.set('err_msg', 'The password needs to be atleast 6 character long.'), livepage.eol
            elif npassword != cpassword:
                yield livepage.set('err_msg', 'The New Password and Confirm Password do not match!'), livepage.eol
            else:
                opsview_dic = dict(zip(opsview_field_names, opsview_values))
                #log.debug("ChangePasswordForm: processchange: opsview_dic=%s"%opsview_dic)    

                for field in opsview_field_names:
                    if field.startswith("login_"):
                        opsview_cred = {}
                        opsview_cred["server_name"] = field.split('_')[1]
                        opsview_cred["login_id"]    = opsview_dic[field]
                        opsview_creds.append(opsview_cred)
                for cred in opsview_creds:
                    cred["password"] = opsview_dic["pass_%s"%cred["server_name"]]
                #log.debug("ChangePasswordForm: opsview_creds=%s"%opsview_creds)

                # Change the password now
                d = subscriber.updatePassword(username      = username,
                                              password      = tpassword,
                                              new_password  = cpassword,
                                              opsview_creds = opsview_creds)
                d.addCallback(onSuccess) 
                d.addErrback(onFailure) 

                yield d
                #yield livepage.set('success_msg', 'Please wait...'), livepage.eol
    
    ######################## Create Page ###########################

    PAGE_STRING = '''
           <html xmlns:nevow="http://nevow.com/ns/nevow/0.1">
           <title>Opsgraph: Change Password</title>
           <head>
                <nevow:invisible nevow:render="liveglue"/>
                <style type="text/css" >
                    #outer {
                         position: absolute;
                          top: 50%%;
                          left: 0px;
                          width: 100%%;
                          height: 1px;
                          overflow: visible;
                          }

                      #inner {
                          width: 400px;
                          height: 300px;
                          margin-left: -200;  /***  width / 2   ***/
                          position: absolute;
                          top: -150px;          /***  height / 2   ***/
                          left: 50%%;
                          }
                      .success_msg {text-align: center; color: green; font-weight: bold}
                      .err_msg {text-align: center; color: red; font-weight: bold}
                </style> 
                <script>
                    function resetForm(){
                        document.getElementById("changepass").reset();
                    }
                </script>
           </head>
           <body>
             <div id="outer">
              <div id="inner">
              <div id="success_msg" class="success_msg"></div>
              <div id="err_msg" class="err_msg"></div>
                  %s
                  <table>
                    <tr><td>Login ID:</td><td><input type="text" id="username" name="username" /></td></tr>
                    <tr><td>Current Password:</td><td><input type="password" id="password" name="password" /></td></tr>
                    <tr><td>New Password:</td><td><input type="password" id="npassword" name="npassword" /></td></tr>
                    <tr><td>Confirm Password:</td><td><input type="password" id="cpassword" name="cpassword" /></td></tr>
                    %s
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"><button type="submit">Change</button></td></tr>
                    <tr><td colspan="2" align="right"> </td></tr>
                    <tr><td colspan="2" align="right"><a href="/">Back to login</a></td></tr>
                 </table>
              </form>
           </div>
         </div></body></html>
    '''%(_generate_formtag(), _generate_opsview_fields())

    #print PAGE_STRING

    docFactory = loaders.xmlstr(PAGE_STRING)


######################################################################################

class ForgotPasswordForm (livepage.LivePage):

    def render_theTitle(self, ctx, data):
        return 'Opsgraph: Forgot Password'

    def renderHTTP_notFound(self, ctx):
        request = inevow.IRequest(ctx)
        request.redirect('/')
        return ''

    def handle_processforgot(self, ctx, *args):
        log.debug("ForgotPasswordForm: processorgot() called - args=%s"%str(args))

        def onSuccess(result, client):
            log.debug("ForgotPasswordForm: onSuccess: result = %s"%str(result))
            client.sendScript(livepage.js('resetForm')())
            yield livepage.set('err_msg', ''), livepage.eol
            yield livepage.set('success_msg', 'A temporary password has been sent to your inbox. You will not be allowed to login until you change your password.'), livepage.eol

        def onFailure(failure, client):
            log.debug("ForgotPasswordForm: onFailure: result = %s"%str(failure))
            errmsg = ''
            try:
                errmsg = failure.getErrorMessage() or ''
            except:
                pass
            yield livepage.set('success_msg', ''), livepage.eol
            yield livepage.set('err_msg', 'Sorry, your password reset was not successful. %s'%errmsg), livepage.eol

        req_args = inevow.IRequest(ctx).args
        client = livepage.IClientHandle(ctx)

        # form validation
        if not args or len(args) < 1:
            yield livepage.set('err_msg', 'Please fill all the fields in the form'), livepage.eol
        else:
            username  = args[0] 

            if not username or len(username) < 1:
                yield livepage.set('err_msg', 'Please enter your graphtool login id.'), livepage.eol
            else:
                # Reset to a temporary password now
                d = subscriber.forgotPassword(username = username)
                d.addCallback(onSuccess, client) 
                d.addErrback(onFailure, client) 

                yield d
    
    ######################## Create Page ###########################

    PAGE_STRING = '''
           <html xmlns:nevow="http://nevow.com/ns/nevow/0.1">
           <title>Opsgraph: Forgot Password</title>
           <head>
                <nevow:invisible nevow:render="liveglue"/>
                <style type="text/css" >
                    #outer {
                         position: absolute;
                          top: 50%;
                          left: 0px;
                          width: 100%;
                          height: 1px;
                          overflow: visible;
                          }

                      #inner {
                          width: 400px;
                          height: 300px;
                          margin-left: -200;  /***  width / 2   ***/
                          position: absolute;
                          top: -150px;          /***  height / 2   ***/
                          left: 50%;
                          }
                      .success_msg {text-align: center; color: green; font-weight: bold}
                      .err_msg {text-align: center; color: red; font-weight: bold}
                </style> 
                <script>
                    function resetForm(){
                        document.getElementById("forgotpass").reset();
                    }
                </script>
           </head>
           <body>
             <div id="outer">
              <div id="inner">
              <div id="success_msg" class="success_msg"></div>
              <div id="err_msg" class="err_msg"></div>
                <form onsubmit="server.handle('processforgot',document.getElementById('username').value); return false;" method="POST" name="forgotpass" id="forgotpass">
                  <table>
                    <tr><td>Login ID:</td><td><input type="text" id="username" name="username" /></td></tr>
                    <tr><td colspan="2" align="center"> </td></tr>
                    <tr><td colspan="2" align="center"> </td></tr>
                    <tr><td colspan="2" align="right"><button type="submit">Send Email</button></td></tr>
                    <tr><td colspan="2" align="center"> </td></tr>
                    <tr><td colspan="2" align="center"> </td></tr>
                    <tr><td align="left"><a href="/change">Change Password</a></td><td align="right"><a href="/">Back to login</a></td></tr>
                 </table>
              </form>
           </div>
         </div></body></html>
    '''

    #print PAGE_STRING

    docFactory = loaders.xmlstr(PAGE_STRING)


######################################################################################

