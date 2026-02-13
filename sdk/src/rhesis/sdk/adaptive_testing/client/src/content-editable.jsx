import React from 'react';
import autoBind from 'auto-bind';
import sanitizeHtml from 'sanitize-html';
import { defer } from 'lodash';

export default class ContentEditable extends React.Component {
  static defaultProps = {
    editable: true,
    defaultText: "",
    finishOnReturn: false
  };

  constructor(props) {
    super(props);
    autoBind(this);
    this.lastText = null;

    this.divRef = {};
    window["cedit_"+this.props.id] = this;
  }

  render() {
    //console.log("this.props.text", this.props.text)
    const emptyContent = this.props.text === undefined || this.props.text.length === 0;
    this.lastEditable = this.props.editable;
    if (this.lastText === null) this.lastText = this.props.text;
    return <div
      ref={(el) => this.divRef = el}
      id={this.props.id}
      style={{opacity: emptyContent ? "0.3" : "1", display: "inline", overflowWrap: "anywhere", whiteSpace: "pre-wrap"}}
      onFocus={this.onFocus}
      onInput={this.handleInput}
      onKeyPress={this.handleKeyPress}
      onKeyDown={this.handleKeyDown}
      onBlur={this.onBlur}
      onDoubleClick={this.handleDoubleClick}
      onDragStart={this.stopDrag}
      onClick={this.onClick}
      contentEditable={this.props.editable}
      className="adatest-editable"
      dangerouslySetInnerHTML={{__html: sanitizeHtml(emptyContent ? this.props.defaultText : this.props.text)}}
      tabIndex="0"
    ></div>
  }

  stopDrag(e) {
    console.log("stopDrag")
    e.preventDefault();
    return false;
  }

  handleDoubleClick(e) {
    const range = getMouseEventCaretRange(e);
    console.log("handleDoubleClick", range, e)
  }

  focus() {

    // we blur without triggering an action so that we can refocus
    // this is important to get the cursor to come back sometimes
    this.skipBlurAction = true;
    this.divRef.blur();
    this.skipBlurAction = false;
    
    this.divRef.focus();
  }

  blur() {
    this.divRef.blur();
  }

  onFocus(e) {
    console.log("onFocus in ContentEditable", this.props.text);

    // if (!this.props.editing) return;
    
    if (this.props.text !== this.props.defaultText && this.divRef.textContent === this.props.defaultText) {
      e.preventDefault();
      e.stopPropagation();
      this.divRef.textContent = "";
      if (this.props.onClick) this.props.onClick(e); // why we need this is crazy to me, seems like setting inner text kills the click event
      // defer(() => this.focus());
      console.log("clear!!", this.props.editable)
      defer(() => this.focus());
    }
  }

  onClick(e) {
    // console.log("onClick in ContentEditable", this.props.onClick)
    if (this.props.onClick) {
      e.preventDefault();
      e.stopPropagation();
      this.props.onClick(e);
    }
    e.stopPropagation();
  }

  getValue() {
    const text = this.divRef.textContent;
    if (text === this.props.defaultText) return "";
    else return text;
  }

  shouldComponentUpdate(nextProps) {
    return nextProps.text !== this.divRef.textContent && (nextProps.text != "" || this.divRef.textContent != this.props.defaultText) || nextProps.editable != this.lastEditable;
  }

  componentDidUpdate() {
    this.componentDidUpdateOrMount(false);
  }

  componentDidMount() {
    this.componentDidUpdateOrMount(true);
  }
  
  componentDidUpdateOrMount(mount) {
    // console.log("ContentEditable componentDidUpdateOrMount", mount, this.props.text, this.props.editable);
    if (this.props.text !== this.divRef.textContent) {
      if (this.props.text !== undefined && this.props.text !== null && (this.props.text.length > 0 || this.divRef.textContent !== this.props.defaultText)) {
        this.divRef.textContent = this.props.text;
      } else {
        if (mount) this.divRef.textContent = this.props.defaultText;
      }
    }
    if (this.props.text && (this.props.text.startsWith("New topic") || this.props.text === "New test") && this.props.editable) { // hacky but works for now
      // console.log("HACK!", this.props.text)
      this.divRef.focus();
      selectElement(this.divRef);
      // document.execCommand('selectAll', false, null);
    }
  }
      
  handleInput(e, finishing) {
    console.log("handleInput", finishing, this.divRef.textContent)
    const text = this.divRef.textContent;
    if (this.props.onInput && text !== this.lastText) {
      this.props.onInput(text);
      this.lastText = text;
    }

    if (finishing && this.props.onFinish) {
      this.props.onFinish(text);
    }

    if (text === this.props.defaultText) this.divRef.style.opacity = 0.3;
    else this.divRef.style.opacity = 1.0;
  }

  onBlur(e) {
    console.log("onBlur in ContentEditable", this.divRef.textContent, this.skipBlurAction)
    if (this.skipBlurAction) return;
    // if (this.divRef.textContent.length === this.props.defaultText) {
    //   this.divRef.textContent = "";
    // }
    this.handleInput(e, true);
    if (this.divRef.textContent.length === 0) {
      this.divRef.textContent = this.props.defaultText;
      this.divRef.style.opacity = 0.3;
    }
  }

  handleKeyPress(e) {

    console.log("handleKeyPress", e.charCode, this.props.finishOnReturn)
    e.stopPropagation();
    if (e.charCode == 13 && this.props.finishOnReturn) {
      e.preventDefault();

      this.handleInput(e, true);
    }
  }

  handleKeyDown(e) {
    console.log("handleKeyDown", e.charCode, this.props.finishOnReturn)
    // only let the enter/return key go through
    if (e.charCode != 13 || !this.props.finishOnReturn) e.stopPropagation();
  }
}

function selectElement(element){
  var doc = document;
  console.log(this, element);
  if (doc.body.createTextRange) {
      var range = document.body.createTextRange();
      range.moveToElementText(element);
      range.select();
  } else if (window.getSelection) {
      var selection = window.getSelection();        
      var range = document.createRange();
      range.selectNodeContents(element);
      selection.removeAllRanges();
      selection.addRange(range);
  }
}

function setCaret(el, pos) {
  var range = document.createRange();
  var sel = window.getSelection();
  
  range.setStart(el, pos)
  range.collapse(true)
  
  sel.removeAllRanges()
  sel.addRange(range)
}
document.setCaret = setCaret;

function findParentWithClass(el, className) {
  const orig_el = el;
  while (el && !el.className.includes(className)) {
    el = el.parentElement;
  }
  return el ? el : orig_el;
}

function getMouseEventCaretRange(evt) {
  var range, x = evt.clientX, y = evt.clientY;

  // Try the simple IE way first
  if (document.body.createTextRange) {
      range = document.body.createTextRange();
      range.moveToPoint(x, y);
  }

  else if (typeof document.createRange != "undefined") {
      // Try Mozilla's rangeOffset and rangeParent properties,
      // which are exactly what we want
      if (typeof evt.rangeParent != "undefined") {
          range = document.createRange();
          range.setStart(evt.rangeParent, evt.rangeOffset);
          range.collapse(true);
      }

      // Try the standards-based way next
      else if (document.caretPositionFromPoint) {
          var pos = document.caretPositionFromPoint(x, y);
          range = document.createRange();
          range.setStart(pos.offsetNode, pos.offset);
          range.collapse(true);
      }

      // Next, the WebKit way
      else if (document.caretRangeFromPoint) {
          range = document.caretRangeFromPoint(x, y);
      }
  }

  return range;
}