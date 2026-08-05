/*
 * Mirrored from World of Dungeons for the 战报网 reader (GAP-005).
 * Source : https://delta.world-of-dungeons.org/wod/javascript/wod_standard.js?1662631467
 * Fetched: 2026-08-05   Version query: 1662631467
 * Note   : Served locally to drop a render-blocking cross-border DNS/TLS
 *          chain. Relative image url() were rewritten to absolute delta
 *          URLs; @import stays local (ajax.css/news.css also mirrored).
 *          Re-fetch and re-run the url() rewrite if the version query bumps.
 */

var SESSION_PLAYER_ID = false
var SESSION_HERO_ID   = false
var SESSION_ARGS      = false
var DEBUG             = false
var PFAD_WOD   = '/wod/spiel/';
var PFAD_AJAX  = '/wod/ajax/';

var WOD_SERVER    = ''
var IS_POPUP      = false
var SKIN          = ''
var LAYOUTCSS     = '/wod/css/'
var GAMETYPE      = 'WOD'
var SPRACHE       = ''
var HAVE_DIAMONDS = false

function time() {
    var now = new Date();
    var now_unix = now.getTime() / 1000

    return now_unix
}



function isChrome() {
    return navigator.userAgent.toLowerCase().indexOf('chrome')!=-1
}

function isSafari2() {
    return navigator.userAgent.toLowerCase().indexOf('safari')!=-1
           && navigator.userAgent.indexOf('Version')==-1
           && navigator.userAgent.toLowerCase().indexOf('chrome')==-1
}

function isIE6() {
    return navigator.userAgent.search(/MSIE 6.+/)!=-1
           && navigator.userAgent.search(/MSIE 7.+/)==-1
}

function isIE() {
    return navigator.userAgent.search(/MSIE.+/)!=-1
}

function trim( s )
{
    if (typeof s=='undefined'
        || s.length<=1)
        return '';

    while (s.charAt(s.length-1) == ' ') {
        s=s.substring(0,s.length-2)
    }

    return s;
}

function _get_base64_coder() {

    TheBase64Coder = {

            // private property
            _keyStr : "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=",

            // public method for encoding
            encode : function (input) {
                    var output = "";
                    var chr1, chr2, chr3, enc1, enc2, enc3, enc4;
                    var i = 0;

                    input = TheBase64Coder._utf8_encode(input);

                    while (i < input.length) {

                            chr1 = input.charCodeAt(i++);
                            chr2 = input.charCodeAt(i++);
                            chr3 = input.charCodeAt(i++);

                            enc1 = chr1 >> 2;
                            enc2 = ((chr1 & 3) << 4) | (chr2 >> 4);
                            enc3 = ((chr2 & 15) << 2) | (chr3 >> 6);
                            enc4 = chr3 & 63;

                            if (isNaN(chr2)) {
                                    enc3 = enc4 = 64;
                            } else if (isNaN(chr3)) {
                                    enc4 = 64;
                            }

                            output = output +
                            this._keyStr.charAt(enc1) + this._keyStr.charAt(enc2) +
                            this._keyStr.charAt(enc3) + this._keyStr.charAt(enc4);

                    }

                    return output;
            },

            // public method for decoding
            decode : function (input) {
                    var output = "";
                    var chr1, chr2, chr3;
                    var enc1, enc2, enc3, enc4;
                    var i = 0;

                    input = input.replace(/[^A-Za-z0-9\+\/\=]/g, "");

                    while (i < input.length) {

                            enc1 = this._keyStr.indexOf(input.charAt(i++));
                            enc2 = this._keyStr.indexOf(input.charAt(i++));
                            enc3 = this._keyStr.indexOf(input.charAt(i++));
                            enc4 = this._keyStr.indexOf(input.charAt(i++));

                            chr1 = (enc1 << 2) | (enc2 >> 4);
                            chr2 = ((enc2 & 15) << 4) | (enc3 >> 2);
                            chr3 = ((enc3 & 3) << 6) | enc4;

                            output = output + String.fromCharCode(chr1);

                            if (enc3 != 64) {
                                    output = output + String.fromCharCode(chr2);
                            }
                            if (enc4 != 64) {
                                    output = output + String.fromCharCode(chr3);
                            }

                    }

                    output = TheBase64Coder._utf8_decode(output);

                    return output;

            },

            // private method for UTF-8 encoding
            _utf8_encode : function (string) {
                    string = string.replace(/\r\n/g,"\n");
                    var utftext = "";

                    for (var n = 0; n < string.length; n++) {

                            var c = string.charCodeAt(n);

                            if (c < 128) {
                                    utftext += String.fromCharCode(c);
                            }
                            else if((c > 127) && (c < 2048)) {
                                    utftext += String.fromCharCode((c >> 6) | 192);
                                    utftext += String.fromCharCode((c & 63) | 128);
                            }
                            else {
                                    utftext += String.fromCharCode((c >> 12) | 224);
                                    utftext += String.fromCharCode(((c >> 6) & 63) | 128);
                                    utftext += String.fromCharCode((c & 63) | 128);
                            }

                    }

                    return utftext;
            },

            // private method for UTF-8 decoding
            _utf8_decode : function (utftext) {
                    var string = "";
                    var i = 0;
                    var c = c1 = c2 = 0;

                    while ( i < utftext.length ) {

                            c = utftext.charCodeAt(i);

                            if (c < 128) {
                                    string += String.fromCharCode(c);
                                    i++;
                            }
                            else if((c > 191) && (c < 224)) {
                                    c2 = utftext.charCodeAt(i+1);
                                    string += String.fromCharCode(((c & 31) << 6) | (c2 & 63));
                                    i += 2;
                            }
                            else {
                                    c2 = utftext.charCodeAt(i+1);
                                    c3 = utftext.charCodeAt(i+2);
                                    string += String.fromCharCode(((c & 15) << 12) | ((c2 & 63) << 6) | (c3 & 63));
                                    i += 3;
                            }

                    }

                    return string;
            }

    }

    return TheBase64Coder
}


function base64_encode(source)
{
    if (typeof source=='undefined' || source=='')
        return '';

    coder = _get_base64_coder()

    return coder.encode( source )
}

function base64_decode(source) {

    if (typeof source=='undefined' || source=='')
        return '';

    coder = _get_base64_coder()

    return coder.decode( source )
}


function ej(typ, uulabel, id, misc)
{
	if (typeof misc != 'undefined')
		return jump(typ,uulabel, id, misc); /* id = HP / misc = ANW */
	else if (id>0)
		return jump(typ,id,uulabel);
	else
		return jump(typ,uulabel);
}

function wodInitialize( host, https, pfad_wod, pfad_ajax, gametype, language, skin_path, layout_css, have_diamonds, is_popup ) {

    if (host == '') {
        WOD_SERVER=''
    } else {

        if (https != '') {
            protocol = 'https://'
        } else {
            protocol = 'http://'
        }

        WOD_SERVER = protocol + host
    }

    PFAD_WOD      = pfad_wod
    PFAD_AJAX     = pfad_ajax
    SKIN          = skin_path
    LAYOUTCSS     = layout_css
    IS_POPUP      = is_popup
    GAMETYPE      = gametype
    SPRACHE       = language
    HAVE_DIAMONDS = have_diamonds
}


function initJsSession( session_player_id, session_hero_id, session_args, debug ) {
    SESSION_ARGS      = session_args
                        + '&session_hero_id=' + session_hero_id
                        + '&session_player_id=' + session_player_id

    DEBUG = debug
}

function inArray( element, list ) {

    if (typeof list != 'object')
        return false

    for (i in list) {
        if (list[i] == element)
            return true
    }
    return false
}

function jump(typ,id,vorlage_id, misc)
{
	var ssesid_local='';

	ssesid_local=SESSION_ARGS;

    var is_integer = typeof id != 'string'
                     || id.match( /^[0-9]{1,}$/ )

    var URL = '';

	if (is_integer)
	{
        switch(typ)
        {
            case 'c':
                URL=PFAD_WOD + 'clan/clan.php?id=' + id + ssesid_local;
                break;
            case 'u':
                URL=PFAD_WOD + 'dungeon/group.php?id=' + id + ssesid_local;
                break;
            case 'h':
                URL=PFAD_WOD + 'hero/profile.php?id=' + id + ssesid_local;
                break;
            case 'i':
                URL=PFAD_WOD + 'hero/item.php?item_instance_id=' + id + '&' + ('string' == typeof vorlage_id ? 'key' : 'vorlage_id') + '=' + vorlage_id + ssesid_local;
                break;
            case 'q':
                URL=PFAD_WOD + 'quests/details.php?id=' + id + ssesid_local;
                break;
        }
    }

    if (!URL) {
		switch(typ)
		{
			case 'p':
				URL=PFAD_WOD + 'profiles/player.php?key=' + id + ssesid_local;
				break;
			case 'h':
				URL=PFAD_WOD + 'hero/profile.php?key=' + id + ssesid_local;
				break;
			case 'm':
				URL=PFAD_WOD + 'help/npc.php?key=' + id + ssesid_local;
				break;
			case 'i':
				URL=PFAD_WOD + 'hero/item.php?key=' + id + ssesid_local;
				break;
			case 'g':
				URL=PFAD_WOD + 'hero/item.php?key=' + id;
				if (typeof misc != 'undefined'){
					URL += '&hp=' + vorlage_id + '&anw=' + misc;
				}
				URL +=  ssesid_local;
				break;
			case 't':
				URL=PFAD_WOD + 'hero/skill.php?key=' + id + ssesid_local;
				break;
			case 'x':
				URL=PFAD_WOD + 'hero/class.php?key=' + id + ssesid_local;
				break;
			case 'u':
				URL=PFAD_WOD + 'dungeon/group.php?key=' + id + ssesid_local;
				break;
			case 'c':
				URL=PFAD_WOD + 'clan/clan.php?key=' + id + ssesid_local;
				break;
			case 'o':
				URL=PFAD_WOD + 'clan/item.php?key=' + id + ssesid_local;
				break;
			case 'e':
				URL=PFAD_WOD + 'help/effect.php?key=' + id + ssesid_local;
				break;

		}
	}

	return wo( WOD_SERVER + URL);
}

function isInternUrl(url) {
    var start = url.substring(0,1);
    return start == '/' || start == '.';
}

function appendGetParam(url, param ) {

    qmark_index = url.indexOf( '?' )
    if (qmark_index<0)
        return url + '?' + param

    anchor = ''
    anchor_index = url.indexOf( '#' )

    if (anchor_index > 0) {
        anchor = url.substr(anchor_index)
        url = url.substr(0,anchor_index)
    }

    if (url[ url.length-1 ]  != '&')
        url = url + '&'

    return url + param + anchor
}

function wo(URL, w, h, id )
{
    var location="location=1,statusbar=1,toolbar=1,"
    if (isInternUrl(URL)) {
        location="location=0,statusbar=0,toolbar=0,"
        var found = URL.search(/is_popup/)
        if (found==-1)
            URL = appendGetParam(URL, 'is_popup=1' )
    }

    if (typeof id == 'undefined') {
        day = new Date()
	    id = day.getTime()
    }

	if (typeof w == 'undefined' || w==0) {
		w=8*screen.width/10

		if (w>900)
		  w=900
	}
	else if (w <= 100) {
		w=w*screen.width/100
	}

	if (typeof h == 'undefined' || h==0)
		h=8*screen.height/10

	else if (h <= 100) {
		h=h*screen.height/100
	}

	x=(screen.width-w)/2
	y=(screen.height-h)/2

	var n = window.open(URL,
	                    id,
	                    location + "scrollbars=1,menubar=0,resizable=1,width=" + w + ",height=" + h + ",left = " + x + ",top = " + y)

    // n==null kann bei Popupblockern passieren, der Browser gibt aber einen Hinweis
    if (n!==null && typeof(n)!='undefined') {
      n.focus()
    }

	return false;
}

/**
 * Parsed einen WoD-Link und �ffnet die passende URL im content frame.
 * @author Michael P. Jung / www.terreon.de
 * @param link Der String, welcher den WoD-Link enth�lt.
 */
function wodlink(link) {

    var re = /^\s*\[\s*([^:]+?)\s*:\s*(.+?)\s*\]\s*$/
	var m = link.match(re)

	var commonargs='&jump=1';

	if (m) {
		var type = m[1]
		var id = m[2]

		id = encodeURIComponent(id)

		switch (type) {
 		case 'npc':
 		case 'beast':
				var url = PFAD_WOD + 'help/npc.php?name=' + id + commonargs
				break
		case 'effect':
				var url = PFAD_WOD + 'help/effect.php?name=' + id + commonargs
				break
		case 'clan':
				var url = PFAD_WOD + 'clan/clan.php?name=' + id + commonargs
				break
	    case 'team':
		case 'group':
				var url = PFAD_WOD + 'dungeon/group.php?name=' + id + commonargs
				break
		case 'hero':
				var codes=''
        		for (i=0; i< m[2].length; i++) {
        		    if (codes!='')
        		          codes = codes + ','
                    codes = codes + m[2].charCodeAt(i)
        		}
				var url = PFAD_WOD + 'hero/profile.php?name=' + id + '&codes=' + codes + commonargs
				break
        case 'player':
                var url = PFAD_WOD + 'profiles/player.php?name=' + id + commonargs
				break
		case 'monument':
				var url = PFAD_WOD + 'clan/item.php?name=' + id + commonargs
				break
		case 'item':
				var url = PFAD_WOD + 'hero/item.php?name=' + id + commonargs
				break
		case 'skill':
				var url = PFAD_WOD + 'hero/skill.php?name=' + id + commonargs
				break
        case 'forum':
                var url = PFAD_WOD + 'forum/viewforum.php?id=' + id + commonargs + '&board=kein';
                break
		case 'post':
				var url = PFAD_WOD + 'forum/viewtopic.php?pid=' + m[2]  + commonargs + '&board=kein#' + m[2];
				break
		case 'pcom':
                t = m[2].split("_")
                if (t.length>=2)
				    var url = PFAD_WOD + 'forum/viewtopic.php?pid=' + t[2]  + commonargs + '&board=' + t[1] + '&world=' + t[0] +'#' + t[2];
				else
				    var url = PFAD_WOD + 'forum/viewtopic.php?pid=' + m[2]  + commonargs + '&board=local#' + m[2];
				break
		case 'auction':
				var url = PFAD_WOD + 'trade/auction_details.php?id=' + m[2]  + commonargs
				break
		case 'murequest':
    			var url = PFAD_WOD + 'admin/murequest.php?request_id=' + m[2]  + commonargs
	       		break;
		case 'murequestadmin':
			    var url = PFAD_WOD + 'admin/murequestadmin.php?request_id=' + m[2]  + commonargs
			    break;
		case 'class':
				var url = PFAD_WOD + 'hero/class.php?name=' + m[2] + commonargs;
				break;
		case 'set':
				var url = PFAD_WOD + 'hero/set.php?name=' + m[2] + commonargs;
				break;
		}
		
		if (url) {
			wo( js_append_params( WOD_SERVER + url, 'IS_POPUP=1' ) )
		} else {
			wo(js_append_params(PFAD_WOD + 'help/nojump.php', commonargs + '&code64=' + encodeURI(base64_encode(link))))
		}
	} else {
		wo(js_append_params(PFAD_WOD + 'help/nojump.php', commonargs + '&code64=' + encodeURI(base64_encode(link))))
	}
	return false
}

function js_append_params(url,params) {
  if (params=="") {
    return url;
  }
  var parts = url.split("#");
  var result = parts[0];
  //result += parts[0]; For some reason, this was there, it makes no sense at all, so now it is gone!
  result += (parts[0].indexOf("?")==-1?"?":"&");
  result += params;
  result += (parts.length==1?"":"#"+parts[1]);
  return result;
}

function js_format(text) {
    text = text.replace(/<br.*?>/g, "\n")
    text = text.replace(/<p*?>/g, "\n\n")

    var temp_div = document.createElement('div');
    temp_div.innerHTML = text;

    return temp_div.firstChild.nodeValue;
}

function js_alert(text) {
    return alert(js_format(text))
}

function js_confirm(text) {
    text = text.replace(/<br.*?>/, "\n")
    return confirm(js_format(text))
}

function js_prompt( text ) {
    text = text.replace(/<br.*?>/, "\n")
    return prompt(js_format(text))
}

function js_readUserInput( inputid, label ) {
    var text = js_prompt( label )

    if (text != '') {
        var inputobj = document.getElementById( inputid )
        inputobj.value = text
        return true
    }

    return false
}

function js_radioButtonValue(rObj) {

    if (typeof rObj.checked == "boolean") {
    	if (rObj.checked)
        	return rObj.value
    	else
    		return false
    }

    for (var i=0; i<rObj.length; i++)
        if (rObj[i].checked)
            return rObj[i].value;
    return false;
}

function js_selectValue(rObj) {
    var index = rObj.selectedIndex
    return rObj.options[index].value
}

function js_selectLabel(rObj) {
    var index = rObj.selectedIndex
    return rObj.options[index].text
}


// state="block" or "none"
function setDisplayState(id, state){

    obj = document.getElementById(id);

    if (typeof obj != 'undefined' && obj != null) {
        obj.style.display = state
    }
}




function toggleDisplayState(id){
    old_display = getDisplayState( id )
    new_display = old_display == 'block' ? 'none' : 'block'
    setDisplayState( id, new_display )
}

function isVisible( id ) {

    var obj = document.getElementById( id );

    if (typeof obj == 'undefined' || obj == null) {
        return false
    }

    var display = obj.style.display

    if (display) {
        return display != 'none'
    }

    var has_hidden_css_class = ajaxCssClassEnabled( obj, 'hidden' )

    return !has_hidden_css_class;
}

function getDisplayState( id ){

    obj = document.getElementById( id );

    if (typeof obj != 'undefined' && obj != null) {
        return obj.style.display
    }

    return '-'
}


/**
 * Setzt den Displaysate fuer alle Elemente, deren ID mit name beginnt.
 * tag is z.B. div, a oder span
 * State ist "block" oder "none"
 */
function setDisplayStateAll( tag, name, state )
{
    var elements = document.getElementsByTagName(tag)
    var len = name.length

    for (var i=0; i<elements.length; i++)
    {
        var obj = elements[i]

        if (obj.id.substring(0, len)==name) {
            setDisplayState( obj.id, state)
        }
    }
}




function setVisibilityTableRow( id, visible ) {

    var display

    if (visible) {
        display = isIE() ? "block" : "table-row"
    } else {
        display = "none"
    }

    setDisplayState( id, display )
}

function setFocusByName( elementName ) {

    var elements = document.getElementsByName( elementName )

    if (elements.length)
        elements[0].focus()
}



function getFirstElementByName( elementName ) {
     var elements = document.getElementsByName( elementName )

    if (elements.length)
        return elements[0]

    return false
}

function debugLog( msg ) {
    if (DEBUG)
        alert(msg)
}




function _array_rand_sort_function( a, b ) {
 return Math.random() >= 0.5
}

function arrayRand( anArray ) {
    anArray.sort( _array_rand_sort_function )
}






function setRecruiterCookie( cookie_domain )
{
    var tokens = location.href.split( '#' )
    var querystring = tokens[1]
    var have_querystring = typeof querystring != 'undefined'

    if (!have_querystring)
    {
        return
    }

    var args = querystring.split( '&' )

    var affiliate=''
    var campaignkey=''

    for (var i=0; i<args.length; i++)
    {
        var arg = args[i]

        var tokens = arg.split( '=' )

        var key = tokens[0]
        var value = tokens[1]

        if (key == 'a_aid'
          || key == 'a'
          || key == 'aid')
        {
            affiliate = value
        }
    }

    if (affiliate)
    {
        var expires = new Date();
        expires.setMonth(expires.getMonth() + 12);

        document.cookie = "ref_type=partner;expires=" + expires
                        + ";domain=."+cookie_domain+";path=/";
        document.cookie = "ref_id=" + affiliate + ";expires=" + expires
                        + ";domain=."+cookie_domain+";path=/";
    }
}