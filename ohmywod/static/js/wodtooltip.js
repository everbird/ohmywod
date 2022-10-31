// WoD Tooltip
//
// By Florian Bauer
// florianx[at]gmx.net
//
// LICENSE
//
// Copyright (c) 2006  Florian Bauer  All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions are
// met:
//   1. Redistributions of source code must retain the above copyright
//      notice, this list of conditions and the following disclaimer as
//      the first lines of this file unmodified.
//   2. Redistributions in binary form must reproduce the above copyright
//      notice, this list of conditions and the following disclaimer in the
//      documentation and/or other materials provided with the distribution.
//
// THIS SOFTWARE IS PROVIDED BY FLORIAN BAUER ``AS IS'' AND ANY EXPRESS OR
// IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
// OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
// IN NO EVENT SHALL FLORIAN BAUER BE LIABLE FOR ANY DIRECT, INDIRECT,
// INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
// NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
// DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
// THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
// THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


/////////////////////////////////////////////////////////////////////////
//// CONFIG BEGIN

var wodToolTip_Class = "tooltip";    // css class of the tooltip defining font, background, border

var wodToolTip_ShowDelay      = 400;   // Delay, until ToolTip is shown, may be 0
var wodToolTip_ShowDelayAjax  = 300;   // dito for tooltip filled by ajax call
var wodToolTip_HideDelay      = 100;   // Delay, until ToolTip is hidden, should be >= 100

var wodToolTip_OffX           = 6;     // horizontal offset from mouse to ToolTip
var wodToolTip_OffY           = 10;    // vertical offset from mouse to ToolTip

var wodToolTip_MaxHeight      = 600;   // The maximum height of the ToolTip
var wodToolTip_MaxWidth       = 840;
var wodToolTip_ScrollBarWidth = 20;    // The width of a scroll bar (not need to be exact)

var wodToolTip_zIndex = 100000008;

//// CONFIG END
/////////////////////////////////////////////////////////////////////////

var wodToolTipWindow = null;
var wodToolTipContent = new Object();
var wodToolTipAjaxUrl = new Object();
var wodToolTipShowTimeout = null;
var wodToolTipHideTimeout = null;
var wodToolTipVisible = false;
var wodToolTipUniqueId = 0;

var wodToolTipCurrentId;
var wodToolTipCurrentMouseX;
var wodToolTipCurrentMouseY;

function wodToolTipGetMaxHeight() {
    if (typeof window.innerHeight != 'undefined'
        && wodToolTip_MaxHeight>0.8 * window.innerHeight)
           return Math.min( wodToolTip_MaxHeight, Math.max( 100, Math.round(0.8 * window.innerHeight) ))
    return wodToolTip_MaxHeight
}

function wodToolTipGetMaxWidth() {
    if (typeof window.innerWidth != 'undefined'
        && wodToolTip_MaxWidth>0.8 * window.innerWidth)
           return Math.min(wodToolTip_MaxWidth, Math.max( 100, Math.round(0.8 * window.innerWidth) ))

    return wodToolTip_MaxWidth
}



function wodToolTipInit()
{
    if(document.createElement)
    {
        wodToolTipWindow = document.createElement("div");
        document.getElementsByTagName("body")[0].appendChild(wodToolTipWindow);
    }
}

function wodToolTipClose() {
    wodToolTipHide()
}

// Use Settings for Tooltips with clickable links/buttons in it.
function wodToolTipSetLinkMode() {

    wodToolTip_OffY = 0
}

function wodToolTipMove(ev)
{
    this.onmousemove = null;
    wodToolTipShow(ev, this);
}

function wodToolTipHideTimed()
{
    wodToolTipVisible = false;
    wodToolTipHideTimeout = null;

    if (isSafari2()) {
        wodToolTipWindow.style.visibility = "hidden";
        document.removeChild(wodToolTipWindow);
    }
    else
    {
        if (window.opera) {
            wodToolTipWindow.style.visibility = "hidden";
            wodToolTipWindow.style.display = "none";
            wodToolTipWindow.parentNode.removeChild(wodToolTipWindow);
            wodToolTipInit();

        } else {
            while(wodToolTipWindow.firstChild)
            {
                wodToolTipWindow.firstChild.style.visibility = "hidden";
                wodToolTipWindow.removeChild(wodToolTipWindow.firstChild);
            }
        }
    }
}


function ajaxToolTip( domObj, renderClassName, ObjectId )
{
    var url = ajaxGetRenderLink( renderClassName, ObjectId )
    wodToolTip( domObj, AJAX_LOADING_ICON, url )
}

function _wodTooltipUniqueId() {
    return  "___wodToolTip_UniqueId__" + wodToolTipUniqueId++
}

function wodToolTip( obj, content, ajax_url )
{
    if(!obj || !content || content=="" || !obj.getAttribute)
        return;


    if(isIE() && window.innerHeight==null) {
        var hr_tag = '<hr style="width: 100px; margin-left: 10px; text-align:left; " />'
        content = content.replace('<hr>',   hr_tag );
        content = content.replace('<hr />', hr_tag );
    }

    var id = obj.getAttribute("id");

    if((!id || id=="") && obj.setAttribute)
    {
        id = _wodTooltipUniqueId()
        obj.setAttribute("id", id, 0);
    }

    if(!id || id=="" || wodToolTipContent[id])
    {
        obj.onmouseover = null;
        return;
    }

    var have_url = typeof ajax_url != 'undefined'
    if (have_url) {
        wodToolTipAjaxUrl[id] = ajax_url
    }

    wodToolTipContent[id] = content;

    obj.onmouseover = wodToolTipShow;
    obj.onmouseout = wodToolTipHide;
    obj.onmousemove = wodToolTipMove;
}

function wodToolTipHide()
{
    if(wodToolTipVisible == false)
    {
        if(wodToolTipShowTimeout)
        {
            window.clearTimeout(wodToolTipShowTimeout);
            wodToolTipShowTimeout = null;
        }
    }
    else
    {
        if(!wodToolTipHideTimeout)
        {
            wodToolTipHideTimeout = window.setTimeout("wodToolTipHideTimed()", wodToolTip_HideDelay);
        }
    }
}

function wodToolTipShowOnToolTip()
{
    if(wodToolTipVisible == true)
    {
        if(wodToolTipHideTimeout)
        {
            window.clearTimeout(wodToolTipHideTimeout);
            wodToolTipHideTimeout = null;
        }
    }
}

function wodToolTipShow(ev, _this)
{
    if(!_this)
        _this = this;

    if(!ev)
        ev = window.event;

    var id;
    if(_this && _this.getAttribute)
        id  = _this.getAttribute("id");

    if(wodToolTipVisible == true)
    {
        if(wodToolTipHideTimeout)
        {
            window.clearTimeout(wodToolTipHideTimeout);
            wodToolTipHideTimeout = null;
        }

        if(id != wodToolTipCurrentId)
            wodToolTipHideTimed();
        else
            return;
    }

    wodToolTipCurrentId = id;

    if(wodToolTipShowTimeout)
        return;

    if(!wodToolTipCurrentId || wodToolTipCurrentId=="" || !wodToolTipContent[wodToolTipCurrentId])
    {
        _this.onmouseover = null;
        _this.onmouseout = null;
        _this.onmousemove = null;
        return;
    }

    if(ev)
    {
        if(ev.clientX)
            wodToolTipCurrentMouseX = ev.clientX;
        else if(ev.pageX)
            wodToolTipCurrentMouseX = ev.pageX;

        if(ev.clientY)
            wodToolTipCurrentMouseY = ev.clientY;
        else if(ev.pageY)
            wodToolTipCurrentMouseY = ev.pageY;
    }

    var is_ajax_call = typeof wodToolTipAjaxUrl[wodToolTipCurrentId] != 'undefined'
                       && wodToolTipAjaxUrl[wodToolTipCurrentId] != ''

    var show_delay = is_ajax_call ? wodToolTip_ShowDelayAjax : wodToolTip_ShowDelay

    wodToolTipShowTimeout = window.setTimeout("wodToolTipShowTimed()", wodToolTip_ShowDelay);
}

function wodToolTipShowTimed()
{
    wodToolTipVisible = true;
    wodToolTipShowTimeout = null;

    var content = document.createElement("div");
    content.style.visibility = "hidden";

    var have_ajax_url = typeof wodToolTipAjaxUrl[wodToolTipCurrentId] != 'undefined'
                        && wodToolTipAjaxUrl[wodToolTipCurrentId] != ''

    if (have_ajax_url) {
        content_div_id = _wodTooltipUniqueId()
        content.setAttribute("id", content_div_id, 0)
    }


    content.innerHTML = wodToolTipContent[wodToolTipCurrentId];
    content.className = wodToolTip_Class;
    content.onmouseover = wodToolTipShowOnToolTip;
    content.onmouseout = wodToolTipHide;
    content.style.maxHeight = wodToolTipGetMaxHeight() + "px";
    content.style.maxWidth  = wodToolTipGetMaxWidth() + "px";

    content.style.overflow = "auto";
    content.style.zIndex = wodToolTip_zIndex;


    content.style.position = "absolute";

    if(isSafari2())
        wodToolTipWindow = document.appendChild(content);
    else
        wodToolTipWindow.appendChild(content);

    var is_absolut_position = isSafari2() || isIE6() || isChrome();
    content.style.position = (is_absolut_position ? "absolute" : "fixed");

    if (have_ajax_url) {
        var ajax_url = wodToolTipAjaxUrl[wodToolTipCurrentId]
        var input_names = ''
        var flags = AJAX_NO_WAIT_CURSOR
        var loading_icon = ''

        var callback_function = function() {
            var obj = document.getElementById( content_div_id )
            _wodTooltipSetSize( obj )
            _wodTooltipMakeVisible( obj )

            wodToolTipContent[wodToolTipCurrentId] = obj.innerHTML
            wodToolTipAjaxUrl[wodToolTipCurrentId] = ''
        }

        ajaxFetchUrl( ajax_url, input_names, content_div_id, loading_icon, callback_function, flags )
    } else {
        _wodTooltipSetSize( content )
        _wodTooltipMakeVisible( content )
    }

}

function _wodTooltipMakeVisible( content ) {
    content.style.visibility = "visible";

    if (window.opera) wodToolTipWindow.style.display = "inline-block";
}


function _wodTooltipSetSize( content ) {

    var offsetX, offsetY, screenWidth, screenHeight;

    if(self.pageYOffset)
    {
        offsetX = self.pageXOffset;
        offsetY = self.pageYOffset;
    }
    else if(document.documentElement && document.documentElement.scrollTop)
    {
        offsetX = document.documentElement.scrollLeft;
        offsetY = document.documentElement.scrollTop;
    }
    else if(document.body)
    {
        offsetX = document.body.scrollLeft;
        offsetY = document.body.scrollTop;
    }

    if (self.innerHeight)
    {
        screenWidth = self.innerWidth
        screenHeight = self.innerHeight
    }
    else if (document.documentElement && document.documentElement.clientHeight)
    {
        screenWidth = document.documentElement.clientWidth;
        screenHeight = document.documentElement.clientHeight;
    }
    else if (document.body)
    {
        screenWidth = document.body.clientWidth;
        screenHeight = document.body.clientHeight;
    }

    if (typeof screenWidth == 'undefined' || screenWidth<=10)
       screenWidth = 800

    if (typeof screenHeight == 'undefined' || screenHeight<=10)
       screenHeight = 600


    var top
    var bottom
    var left
    var right

    if(wodToolTipCurrentMouseY + wodToolTip_OffY + content.offsetHeight > screenHeight-wodToolTip_ScrollBarWidth)
    {
        bottom = wodToolTip_OffY;

        if (content.offsetHeight < screenHeight - 2 * wodToolTip_ScrollBarWidth) {
            top = screenHeight - content.offsetHeight - wodToolTip_ScrollBarWidth - wodToolTip_OffY
        } else
            top = wodToolTip_OffY
    }
    else
    {
        top = wodToolTipCurrentMouseY + wodToolTip_OffY ;
        bottom = screenHeight
                      - (wodToolTipCurrentMouseY
                         + wodToolTip_OffY
                         + content.offsetHeight
                         + wodToolTip_ScrollBarWidth)
    }

    if(wodToolTipCurrentMouseX + wodToolTip_OffX + content.offsetWidth > screenWidth-wodToolTip_ScrollBarWidth)
    {

        right = wodToolTip_OffX

        if (content.offsetWidth < screenWidth - 2 * wodToolTip_ScrollBarWidth) {

            left = screenWidth - content.offsetWidth - wodToolTip_ScrollBarWidth - wodToolTip_OffX
        } else
            left = wodToolTip_OffX
    }
    else
    {
        left = wodToolTipCurrentMouseX + wodToolTip_OffX

        right = screenWidth
                - (wodToolTipCurrentMouseX
                   + wodToolTip_OffX
                   + content.offsetWidth
                   + wodToolTip_ScrollBarWidth)
    }

    var is_absolut_position = isSafari2() || isIE6() || isChrome();
    if (is_absolut_position) {
        top    += offsetY
        bottom -= offsetY
        left   += offsetX
        right  -= offsetX
    }

    content.style.top    = top    + 'px'
    content.style.bottom = bottom + 'px'
    content.style.left   = left   + 'px'
    content.style.right  = right  + 'px'

}