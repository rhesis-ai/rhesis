import React from 'react';
import autoBind from 'auto-bind';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome'
import { faPlus, faFolderPlus, faCheck, faTimes, faChevronDown, faRedo, faFilter } from '@fortawesome/free-solid-svg-icons'
import { defer, debounce, clone, get } from 'lodash';
import { finishTopicDescription, generateSuggestions, redraw, clearSuggestions, setFirstModel, changeGenerator, changeMode, addTopic, addTest, changeFilter, changeTopic, moveTest, deleteTest } from './CommEvent';
import JupyterComm from './jupyter-comm'
import WebSocketComm from './web-socket-comm'
import Row from './row';
import BreadCrum from './bread-crum';
import TotalValue from './total-value';
import ContentEditable from './content-editable';

export default class Browser extends React.Component {
  constructor(props) {
    super(props);
    autoBind(this);

    // our starting state 
    this.state = {
      topic: "/",
      suggestions: [],
      tests: [],
      selections: {},
      user: "anonymous",
      loading_suggestions: false,
      max_suggestions: 10,
      suggestions_pos: 0,
      suggestionsDropHighlighted: 0,
      score_filter: 0.3,
      do_score_filter: true,
      filter_text: "",
      experiment_pos: 0,
      timerExpired: false,
      experiment_locations: [],
      experiment: false,
      value2Filter: ""
    };

    console.log("this.props.location", this.props.location)

    this.id = 'browser';

    this.rows = {};

    // connect to the jupyter backend
    console.log("pairs this.props.interfaceId", this.props.interfaceId)
    if (this.props.environment === "jupyter") {
      this.comm = new JupyterComm(this.props.interfaceId, this.connectionOpen);
    } else if (this.props.environment === "web") {
      this.comm = new WebSocketComm(this.props.interfaceId, this.props.websocket_server, this.connectionOpen);
    } else {
      console.error("Unknown environment:", this.props.environment);
    }
    this.comm.subscribe(this.id, this.newData);

    this.debouncedForceUpdate = debounce(this.debouncedForceUpdate, 100);

    window.pair_chart = this;
  }

  debouncedForceUpdate() {
    // console.log("debouncedForceUpdate");
    this.forceUpdate();
  }

  // gets called once we have a working websocket connection ready to go
  connectionOpen() {
    // if we are in Jupyter we need to sync the URL in the MemoryRouter
    if (this.props.environment == "jupyter") {
      this.props.history.push(this.props.prefix + this.props.startingTopic);

    // if we don't have a starting topic then we are stand-alone and need to sync our state with the address bar
    } else if (this.props.location.pathname !== (this.props.prefix == "" ? "/" : this.props.prefix)) {
      defer(() => this.goToTopic(this.stripPrefix(this.props.location.pathname)));
    }
    this.props.history.listen(this.locationChanged);

    defer(() => this.comm.sendEvent(redraw()));
  }

  stripPrefix(path) {
    if (path.startsWith(this.props.prefix)) {
      return path.slice(this.props.prefix.length);
    } else {
      return path;
    }
  }

  componentDidUpdate() {
    this.componentDidUpdateOrMount(false);
  }

  componentDidMount() {
    this.componentDidUpdateOrMount(true);
  }
  
  componentDidUpdateOrMount(mount) {
    // console.log("Row componentDidUpdateOrMount", mount, this.state.selections)
    if (Object.keys(this.state.selections).length === 0) {
      // this.divRef.focus();
    }
  }



  render() {
    console.log("----- render AdaTest browser -----", )
    // compute the width of the largest type selection option (used to size the type column)
    let selectWidths = {};
    for (const i in this.state.test_types) {
      const type = this.state.test_types[i];
      // console.log("type", type, this.state.test_type_parts[type])
      // text2 is the part of the test shown in the select, +7 is for spaces on either side
      selectWidths[type] = this.calculateTextWidth(this.state.test_type_parts[type].text2); 
    }
    // let maxInputLength = Math.max(
    //   ...this.state.suggestions.map(id => this.comm.data[id] ? this.comm.data[id].input.length : 1),
    //   ...this.state.tests.map(id => this.comm.data[id] ? this.comm.data[id].input.length : 1)
    // );
    let maxOutputLength = Math.max(
      ...this.state.suggestions.map(id => this.comm.data[id] && this.comm.data[id].output ? this.comm.data[id].output.length : 1),
      ...this.state.tests.map(id => this.comm.data[id] && this.comm.data[id].output ? this.comm.data[id].output.length : 1)
    );
    let outputColumnWidth = "45%";
    if (maxOutputLength < 25) {
      outputColumnWidth = "150px";
    } else if (maxOutputLength < 40) {
      outputColumnWidth = "250px";
    }

    let maxSelectWidth = 40;

    const inFillin = this.state.topic.startsWith("/Fill-ins");

    // console.log("location.pathname", location.pathname);

    let totalPasses = {};
    let totalFailures = {};
    this.totalPassesObjects = {};
    this.totalFailuresObjects = {};
    if (this.state.score_columns) {
      for (const k of this.state.score_columns) {
        // console.log("k", k)
        totalPasses[k] = <TotalValue activeIds={this.state.tests} ref={(el) => {this.totalPassesObjects[k] = el}} />;
        totalFailures[k] = <TotalValue activeIds={this.state.tests} ref={(el) => {this.totalFailuresObjects[k] = el}} />;
        // console.log("totalPasses", totalPasses)
      }
    }
    let topicPath = "";
    // console.log("tests.render4", this.state.tests, stripSlash(this.stripPrefix(this.props.location.pathname)), this.state.topic);

    // Always include root ("") as first element, then topic parts
    const topicStr = stripSlash(this.stripPrefix(this.state.topic));
    let breadCrumbParts = topicStr === "" ? [""] : ["", ...topicStr.split("/")];
    // let totalPasses = <TotalValue activeIds={this.state.tests} ref={(el) => this.totalPassesObj = el} />;
    // let totalFailures = <TotalValue activeIds={this.state.tests} ref={(el) => this.totalFailuresObj = el} />;

    return (<div onKeyDown={this.keyDownHandler} tabIndex="0" style={{outline: "none"}} ref={(el) => this.divRef = el}>
      <div title="Add a new test" onClick={this.addNewTest} style={{float: "right", padding: "9px 10px 7px 14px", border: "1px solid rgb(208, 215, 222)", cursor: "pointer", display: "inline-block", borderRadius: "7px", marginTop: "16px", background: "rgb(246, 248, 250)"}}>
        <div style={{opacity: "0.6", width: "15px", height: "15px", display: "inline-block"}}><FontAwesomeIcon icon={faPlus} style={{fontSize: "13px", color: "#000000", display: "inline-block"}} /></div>
        {/* <span style={{opacity: "0.6", fontSize: "13px", fontWeight: "bold"}}>&nbsp;New Test</span> */}
      </div>
      <div title="Add a new topic" onClick={this.addNewTopic} style={{float: "right", marginRight: "10px", padding: "9px 10px 7px 14px", cursor: "pointer", border: "1px solid rgb(208, 215, 222)", display: "inline-block", borderRadius: "7px", marginTop: "16px", background: "rgb(246, 248, 250)"}}>
        <div style={{opacity: "0.6", width: "15px", height: "15px", display: "inline-block"}}><FontAwesomeIcon icon={faFolderPlus} style={{fontSize: "13px", color: "#000000", display: "inline-block"}} /></div>
        {/* <span style={{opacity: "0.6", fontSize: "13px", fontWeight: "bold"}}>&nbsp;New Topic</span> */}
      </div>
      <div style={{float: "right", marginRight: "10px", padding: "8px 10px 7px 14px", width: "250px", border: "1px solid rgb(208, 215, 222)", display: "inline-block", borderRadius: "7px", marginTop: "16px", background: "rgb(246, 248, 250)"}}>
        <div style={{opacity: "0.6", width: "15px", height: "15px", display: "inline-block", paddingLeft: "1px", marginRight: "10px"}}><FontAwesomeIcon icon={faFilter} style={{fontSize: "13px", color: "#000000", display: "inline-block"}} /></div>
        <span style={{opacity: "0.6", fontSize: "13px", fontWeight: "normal"}}>
          <ContentEditable defaultText="filter tests" text={this.state.filter_text} onFinish={this.inputFilterText} />
        </span>
      </div>
      

      <div style={{paddingTop: '20px', width: '100%', verticalAlign: 'top', textAlign: "center"}}>
        <div style={{textAlign: "left", marginBottom: "0px", paddingLeft: "5px", paddingRight: "5px", marginTop: "-6px", marginBottom: "-14px"}}>
          {/* {this.state.score_columns && this.state.score_columns.slice().reverse().map(k => {
            return <div key={k} style={{float: "right", width: "110px", textAlign: "center"}}>
              {k != "model score" && <div style={{marginTop: "-20px", marginBottom: "20px", height: "0px", cursor: "pointer"}} onClick={e => this.clickModel(k, e)}>{k.replace(" score", "")}</div>}
            </div>
          })} */}
          <span style={{fontSize: "16px"}}>
          {breadCrumbParts.map((name, index) => {
            //console.log("bread crum", name, index);
            // name = decodeURIComponent(name);
            const out = <span key={index} style={{color: index === breadCrumbParts.length - 1 ? "black" : "rgb(9, 105, 218)" }}>
              {index > 0 && <span style={{color: "black"}}> / </span>}
              <BreadCrum topic={topicPath} name={name} defaultName={this.state.test_tree_name} onDrop={this.onDrop} onClick={this.setLocation} />
            </span>
            if (index !== 0) topicPath += "/";
            topicPath += name;
            return index === 0 && this.props.checklistMode ? undefined : out;
          })}
          </span>
          <div style={{clear: "both"}}></div>
          <div></div>
        </div>
        <div style={{textAlign: "left", color: "#999999", paddingLeft: "5px", marginBottom: "-2px", height: "15px"}}>
          <ContentEditable defaultText="No topic description" text={this.state.topic_description} onFinish={this.finishTopicDescription} />
        </div>
        <div clear="all"></div>

        {!this.state.read_only && <div className={this.state.suggestionsDropHighlighted ? "adatest-drop-highlighted adatest-suggestions-box" : "adatest-suggestions-box"} style={{paddingTop: "39px"}} onDragOver={this.onSuggestionsDragOver} onDragEnter={this.onSuggestionsDragEnter}
          onDragLeave={this.onSuggestionsDragLeave} onDrop={this.onSuggestionsDrop}>
          <div className="adatest-scroll-wrap" style={{maxHeight: 31*this.state.max_suggestions, overflowY: "auto"}} ref={(el) => this.suggestionsScrollWrapRef = el}>
            {this.state.suggestions
                //.slice(this.state.suggestions_pos, this.state.suggestions_pos + this.state.max_suggestions)
                // .filter(id => {
                //   //console.log("Math.max(...this.comm.data[id].scores.map(x => x[1]))", Math.max(...this.comm.data[id].scores.map(x => x[1])))
                //   return this.comm.data[id] && this.comm.data[id].scores && Math.max(...this.comm.data[id].scores.map(x => x[1])) > 0.3
                // })
                .map((id, index) => {
              return <React.Fragment key={id}>
                <Row
                  id={id}
                  ref={(el) => this.rows[id] = el}
                  topic={this.state.topic}
                  isSuggestion={true}
                  topicFilter={this.state.topicFilter}
                  value1Filter={this.state.value1Filter}
                  comparatorFilter={this.state.comparatorFilter}
                  value2Filter={this.state.value2Filter}
                  value1Default="New value"
                  value2Default="New value"
                  value2Edited={this.value2Edited}
                  selected={this.state.selections[id]}
                  soleSelected={this.state.selections[id] && Object.keys(this.state.selections).length == 1}
                  onSelectToggle={this.toggleSelection}
                  comm={this.comm}
                  scoreFilter={this.state.do_score_filter && this.state.suggestions.length > this.state.max_suggestions && index > this.state.max_suggestions-4 && this.state.score_filter}
                  selectWidth={maxSelectWidth}
                  forceRelayout={this.debouncedForceUpdate}
                  inFillin={inFillin}
                  scrollParent={this.suggestionsScrollWrapRef}
                  giveUpSelection={this.removeSelection}
                  scoreColumns={this.state.score_columns}
                  test_types={this.state.test_types}
                  test_type_parts={this.state.test_type_parts}
                  user={this.state.user}
                  outputColumnWidth={outputColumnWidth}
                />
              </React.Fragment>
            })}
            {/* {this.state.do_score_filter && this.state.suggestions.length > this.state.max_suggestions &&
              <div onClick={e => this.removeScoreFilter(e)} className="adatest-row-add-button adatest-hover-opacity" style={{lineHeight: "25px", display: "inline-block",}}>
                <FontAwesomeIcon icon={faChevronDown} style={{fontSize: "14px", color: "#000000", display: "inline-block"}} />
              </div>
            } */}
            <div style={{height: "15px"}}></div>
          </div>
          
          <div className="adatest-suggestions-box-after"></div>
          <div style={{position: "absolute", top: "10px", width: "100%"}}>
            {this.state.suggestions.length > 1 &&
              <div onClick={this.clearSuggestions} className="adatest-row-add-button adatest-hover-opacity" style={{marginTop: "0px", left: "6px", top: "4px", width: "11px", lineHeight: "14px", cursor: "pointer", position: "absolute", display: "inline-block"}}>
                <FontAwesomeIcon icon={faTimes} style={{fontSize: "14px", color: "#000000", display: "inline-block"}} />
              </div>
            }
            {!this.state.disable_suggestions && 
              <div onClick={this.refreshSuggestions} style={{color: "#555555", cursor: "pointer", display: "inline-block", padding: "2px", paddingLeft: "15px", paddingRight: "15px", marginBottom: "5px", background: "rgba(221, 221, 221, 0)", borderRadius: "7px"}}>
                <div style={{width: "15px", display: "inline-block"}}><FontAwesomeIcon className={this.state.loading_suggestions ? "fa-spin" : ""} icon={faRedo} style={{fontSize: "13px", color: "#555555", display: "inline-block"}} /></div>
                <span style={{fontSize: "13px", fontWeight: "bold"}}>&nbsp;&nbsp;Suggest {this.state.mode}</span>
                {this.state.generator_options && this.state.generator_options.length > 1 &&
                <select dir="rtl" title="Current suggestion engine" className="adatest-plain-select" onClick={e => e.stopPropagation()} value={this.state.active_generator} onChange={this.changeGenerator} style={{position: "absolute", color: "rgb(170, 170, 170)", marginTop: "1px", right: "13px"}}>
                  {this.state.generator_options.map((generator_option) => {
                    return <option key={generator_option}>{generator_option}</option>
                  })}
                </select>
                }
              </div>
            }
            {this.state.suggestions_error && 
              <div style={{cursor: "pointer", color: "#990000", display: "block", fontWeight: "bold", padding: "2px", paddingLeft: "15px", paddingRight: "15px", marginTop: "-5px"}}>
                {this.state.suggestions_error}
              </div>
            }
            {/* {this.state.loading_suggestions && this.state.tests.length < 5 &&
              <div style={{cursor: "pointer", color: "#995500", display: "block", fontWeight: "normal", padding: "2px", paddingLeft: "15px", paddingRight: "15px", marginTop: "-5px"}}>
                Warning: Auto-suggestions may perform poorly with less than five tests in the current topic!
              </div>
            } */}
          </div>
        </div>}

        <div style={{textAlign: "right", paddingRight: "12px", marginTop: "5px", marginBottom: "-5px", color: "#666666"}}>
          <div style={{width: "200px", textAlign: "right", display: "inline-block"}}>
            Input
          </div>
          <div style={{width: "25px", textAlign: "left", display: "inline-block"}}>
            
          </div>
          <div style={{width: outputColumnWidth, textAlign: "left", display: "inline-block"}}>
            Output
          </div>
          <div style={{width: "50px", textAlign: "center", display: "inline-block", marginRight: "0px"}}>
            <nobr>Off-topic</nobr>
          </div>
          <div style={{width: "50px", textAlign: "center", display: "inline-block", marginRight: "0px"}}>
            Pass
          </div>
          <div style={{width: "50px", textAlign: "center", display: "inline-block", marginRight: "0px"}}>
            Fail
          </div>
        </div>
        
        <div className="adatest-children-frame">
          {this.state.tests.length == 0 && <div style={{textAlign: "center", fontStyle: "italic", padding: "10px", fontSize: "14px", color: "#999999"}}>
            This topic is empty. Click the plus (+) button to add a test.
          </div>}
          {this.state.tests.map((id, index) => {
            return <React.Fragment key={id}>
              <Row
                id={id}
                ref={(el) => this.rows[id] = el}
                topic={this.state.topic}
                hideBorder={index == 0}
                topicFilter={this.state.topicFilter}
                value1Filter={this.state.value1Filter}
                comparatorFilter={this.state.comparatorFilter}
                value2Filter={this.state.value2Filter}
                value2Edited={this.value2Edited}
                selected={this.state.selections[id]}
                soleSelected={this.state.selections[id] && Object.keys(this.state.selections).length == 1}
                onOpen={this.setLocation}
                onSelectToggle={this.toggleSelection}
                onDrop={this.onDrop}
                updateTotals={(k, passes, failures) => {
                  if (this.totalPassesObjects[k]) {
                    this.totalPassesObjects[k].setSubtotal(id, passes);
                    this.totalFailuresObjects[k].setSubtotal(id, failures);
                  }
                }}
                comm={this.comm}
                selectWidth={maxSelectWidth}
                forceRelayout={this.debouncedForceUpdate}
                inFillin={inFillin}
                scrollParent={document.body}
                generateTopicName={this.generateTopicName}
                setSelected={this.setSelected}
                scoreColumns={this.state.score_columns}
                test_types={this.state.test_types}
                test_type_parts={this.state.test_type_parts}
                user={this.state.user}
                outputColumnWidth={outputColumnWidth}
              />
            </React.Fragment>
          })}
        </div>
        {this.state.score_columns && this.state.score_columns.length > 1 &&
          <div style={{textAlign: "right", paddingRight: "12px", marginTop: "5px", marginBottom: "-5px", color: "#666666"}}>
            <div style={{width: "200px", textAlign: "right", display: "inline-block"}}>
              Input
            </div>
            <div style={{width: "25px", textAlign: "left", display: "inline-block"}}>
              
            </div>
            <div style={{width: "171px", textAlign: "left", display: "inline-block"}}>
              Output
            </div>
            <div style={{width: "50px", textAlign: "left", display: "inline-block", marginRight: "8px"}}>
              Label
            </div>
            {this.state.score_columns.map(k => {
              return  <span key={k} style={{display: "inline-block", textAlign: "center", marginLeft: "8px", width: "100px", cursor: "pointer"}} onClick={e => this.clickModel(k, e)}>
                {k.replace(" score", "")}
              </span>
            })}
          </div>
        }
      </div>

      <div style={{textAlign: "right", paddingRight: "11px"}}>
        {this.state.score_columns && this.state.score_columns.map(k => {
          return  <span key={k} style={{display: "inline-block", textAlign: "center", marginLeft: "8px"}}>
            <div onClick={this.onOpen} className="adatest-top-add-button" style={{marginRight: "0px", marginLeft: "0px", color: "rgb(26, 127, 55)", width: "50px", lineHeight: "14px", textAlign: "center", paddingLeft: "0px", paddingRight: "0px", display: "inline-block"}}>
              <FontAwesomeIcon icon={faCheck} style={{fontSize: "17px", color: "rgb(26, 127, 55)", display: "inline-block"}} /><br />
              <span style={{lineHeight: "20px"}}>{totalPasses[k]}</span>
              {/* <span style={{lineHeight: "20px"}}>{this.state.tests.reduce((total, value) => total + this.rows[value].totalPasses["score"], 0)}</span> */}
            </div>
            <div onClick={this.onOpen} className="adatest-top-add-button" style={{marginRight: "0px", marginLeft: "0px", color: "rgb(207, 34, 46)", width: "50px", lineHeight: "14px", textAlign: "center", paddingRight: "0px", display: "inline-block"}}>
              <FontAwesomeIcon icon={faTimes} style={{fontSize: "17px", color: "rgb(207, 34, 46)", display: "inline-block"}} /><br />
              <span style={{lineHeight: "20px"}}>{totalFailures[k]}</span>
            </div>
          </span>
        })}
      </div>
    </div>);
  }

  clickComparatorFilter(e) {
    console.log("clickComparatorFilter", e);
    // e.preventDefault();
    // e.stopPropagation();
    // defer(() => this.comparatorFilterEditable.focus());

    // if (!this.state.comparatorFilterEditing) {
    //   this.setState({comparatorFilterEditing: true});
    //   console.log("clickComparatorFilter editing", this.state.comparatorFilterEditing)
    //   e.preventDefault();
    //   e.stopPropagation();
    //   defer(() => this.value1Editable.focus());
    // }
  }

  clickModel(modelName, e) {
    if (modelName !== this.state.score_columns[0]) {
      this.sendEvent(setFirstModel(modelName));
    }
  }

  // get the display width of some text
  calculateTextWidth(text) {
    var div = document.createElement('div');
    div.setAttribute('class', 'adatest-select-width-calculation');
    div.innerText = text;
    document.body.appendChild(div);
    var width = div.offsetWidth;
    div.parentNode.removeChild(div);
    return width;
  }

  // This is a poor man's hack for what should eventually be multiple cursors
  value2Edited(id, old_value, new_value) {
    const keys = Object.keys(this.state.selections);
    console.log("value2Editedcccccc", id, old_value, new_value, keys)
    if (keys.length > 1 && this.state.selections[id]) {
      for (const k in this.state.selections) {
        console.log("K", k, this.comm.data[k].value2, id)
        if (k !== id && this.rows[k].state.value2 === old_value) {
          // console.log("setting new value", new_value)
          this.rows[k].setValue2(new_value);
        }
      }
    }
  }

  setSelected(id) {
    console.log("setSelected", id)
    let selections = {};
    selections[id] = true;
    this.setState({selections: selections});
  }

  removeSelection(id) {
    console.log("removeSelection", id)
    let newId = undefined;
    const ids = this.state.suggestions.concat(this.state.tests);
    for (let i = 0; i < ids.length; i++) {
      console.log(i, ids[i], id);
      if (ids[i] === id) {
        console.log(i, ids[i]);
        if (i+1 < ids.length) {
          console.log("i+1", i+1, ids[i+1]);
          newId = ids[i+1];
        } else if (i > 0) {
          console.log("i-1", i-1, ids[i-1]);
          newId = ids[i-1];
        }
        break;
      }
    }

    // change our selection to the new id
    if (newId !== undefined) {
      console.log(newId);
      let selections = {};
      selections[newId] = true;
      this.setState({selections: selections});
    }
  }

  changeGenerator(e) {
    this.comm.sendEvent(changeGenerator(e.target.value));
    this.setState({active_generator: e.target.value})
  }

  changeMode(e) {
    this.comm.sendEvent(changeMode(e.target.value));
    this.setState({mode: e.target.value});
  }

  setLocation(pathname) {
    console.log("setLocation", pathname);
    this.props.history.push(this.props.prefix + pathname);
    this.setState({selections: {}});
  }

  locationChanged(location, action) {
    console.log("locationChanged", location, action);
    this.goToTopic(this.stripPrefix(location.pathname));
  }

  newData(data) {
    if (data === undefined) return;

    if (data && "suggestions" in data && !("loading_suggestions" in data)) {
      data["loading_suggestions"] = false;
    }

    console.log("data", data);

    // always select new topics for renaming when they exist
    for (let i in data.tests) {
      if (data.tests[i].startsWith("/New topic")) {
        data.selections = {};
        data.selections[data.tests[i]] = true;
        break;
      }
    }

    // select the first suggestion if we have several and there is no current selection
    if (Object.keys(this.state.selections).length === 0 && data.suggestions.length > 1) {
      data.selections = {};
      data.selections[data.suggestions[0]] = true;
    }
    
    this.setState(data);

    // TODO: this is just a hack for the Checklist baseline user study
    defer(() => {
      //console.log("this.state.suggestions", this.state.suggestions, this.suggestionsTemplateRow.state.value2);
      // fill in the value of the template output if it is blank and we have a guess
      if (this.state.suggestions && this.suggestionsTemplateRow && (this.suggestionsTemplateRow.state.value2 === null || this.suggestionsTemplateRow.state.value2 === "")) {
        
        const key = this.state.suggestions[this.state.suggestions.length - 1];
        //console.log("key", key, Object.keys(this.comm.data))
        if (key in this.comm.data) {
          //console.log("DDFSSS")
          this.suggestionsTemplateRow.setState({value2: this.comm.data[key].value2, comparator: this.comm.data[key].comparator});
        }
      }
    });
  }

  clockFinished() {
    console.log("clockFinished")
    this.setState({
      timerExpired: true
    });
    setTimeout(() => {
      this.setState({
        timerExpired: false,
        experiment_pos: this.state.experiment_pos + 1
      });
      var loc = this.state.experiment_locations[this.state.experiment_pos].location;
      if (loc.startsWith("//")) { // double slash is used to get out of the current test tree
        window.location = loc.slice(1);
      } else if (loc.startsWith("/")) {
        this.setLocation(loc);
      } else {
        window.location = loc;
      }
    }, 5000);
  }

  openTests() {
    this.props.history.push("/Tests")
  }

  openFillins() {
    this.props.history.push("/Fill-ins")
  }

  keyDownHandler(e) {
    let newId = undefined;
    const passKey = 86;
    const failKey = 66;
    const offTopicKey = 67;
    console.log("keyCodeXX", e.keyCode);
    if (e.keyCode == 8 || e.keyCode == 46 || e.keyCode == passKey || e.keyCode == failKey || e.keyCode == offTopicKey) { // backspace and delete and labeling keys
      const keys = Object.keys(this.state.selections);
      const ids = this.state.suggestions.concat(this.state.tests);
      if (keys.length > 0) {

        let in_suggestions = true;
        for (const i in keys) {
          if (!this.state.suggestions.includes(keys[i])) {
            in_suggestions = false;
          }
        }

        if (e.keyCode == offTopicKey && !in_suggestions) { // when marking for out of topic we only do this for suggestion rows
          return;
        }

        if (e.keyCode == passKey) {
          const keys = Object.keys(this.state.selections);
          if (keys.length > 0) {
            for (const i in keys) {
              this.rows[keys[i]].labelAsPass();
            }
          }
        } else if (e.keyCode == failKey) {
          const keys = Object.keys(this.state.selections);
          if (keys.length > 0) {
            for (const i in keys) {
              this.rows[keys[i]].labelAsFail();
            }
          }
        } else if (e.keyCode == offTopicKey) {
          const keys = Object.keys(this.state.selections);
          if (keys.length > 0) {
            for (const i in keys) {
              this.rows[keys[i]].labelAsOffTopic();
            }
          }
        } else {
          this.comm.sendEvent(deleteTest(keys));
        }

        // select the next test after the selected one when appropriate
        if (in_suggestions || e.keyCode == 8 || e.keyCode == 46) {
          let lastId = undefined;
          for (const i in ids) {
            if (this.state.selections[lastId] !== undefined && this.state.selections[ids[i]] === undefined) {
              newId = ids[i];
              break;
            }
            lastId = ids[i];
          }
          let selections = {};
          if (newId !== undefined) selections[newId] = true;
          this.setState({selections: selections});
        }
      }
    } else if (e.keyCode == 38 || e.keyCode == 40) {
      const keys = Object.keys(this.state.selections);
      const ids = this.state.suggestions.concat(this.state.tests);
      if (keys.length == 1) {
        const currId = keys[0];
        let lastId = undefined;
        for (const i in ids) {
          if (e.keyCode == 38 && ids[i] === currId) { // up arrow
            newId = lastId;
            break; 
          }
          if (e.keyCode == 40 && currId === lastId) { // down arrow
            newId = ids[i];
            break;
          }
          lastId = ids[i];
        }
        console.log(" arrow!", lastId, currId);
      } else if (keys.length === 0) {
        if (this.state.suggestions.length > 1) {
          newId = this.state.suggestions[0];
        } else {
          newId = this.state.tests[0];
        }
      }
      console.log(" arrow!", keys, newId);

    } else {
      return;
    }
    e.preventDefault();
    e.stopPropagation();

    // change our selection to the new id
    if (newId !== undefined) {
      let selections = {};//clone(this.state.selections);
      selections[newId] = true;
      this.setState({selections: selections});
    }
  }

  
  removeScoreFilter(e) {
    e.preventDefault();
    e.stopPropagation();

    this.setState({do_score_filter: false});
  }

  generateTopicName() {

    // get a unique new topic name
    let new_topic_name = "New topic";
    let suffix = "";
    let count = 0;
    while (this.state.tests.includes(this.state.topic + "/" + new_topic_name + suffix)) {
      count += 1;
      suffix = " " + count;
    }
    new_topic_name = new_topic_name + suffix

    return new_topic_name;
  }

  addNewTopic(e) {
    e.preventDefault();
    e.stopPropagation();
    this.comm.sendEvent(addTopic())
  }

  addNewTest(e) {
    e.preventDefault();
    e.stopPropagation();
    this.comm.sendEvent(addTest())
  }

  // inputTopicDescription(text) {
  //   this.setState({topic_description: text});
  // }

  finishTopicDescription(text) {
    console.log("finishTopicDescription", text)
    
    this.setState({topic_description: text});
    this.comm.sendEvent(finishTopicDescription(this.state.topic_marker_id, text));
  }

  inputFilterText(text) {
    console.log("inputFilterText", text)
    this.setState({filter_text: text});
    this.comm.sendEvent(changeFilter(text));
  }

  // inputSuggestionsTemplate(text) {
  //   this.setState({suggestionsTemplate: text});
  // }

  // inputValue1Filter(text) {
  //   this.setState({value1Filter: text});
  // }
  
  // inputComparatorFilter(text) {
  //   this.setState({comparatorFilter: text});
  // }

  // inputTopicFilter(text) {
  //   this.setState({topicFilter: text});
  // }


  refreshSuggestions(e) {
    e.preventDefault();
    e.stopPropagation();
    console.log("refreshSuggestions");
    if (this.state.loading_suggestions) return;
    for (let k in Object.keys(this.state.selections)) {
      if (this.state.suggestions.includes(k)) {
        delete this.state.selections[k];
      }
    }
    this.setState({suggestions: [], loading_suggestions: true, suggestions_pos: 0, do_score_filter: true});
    this.comm.sendEvent(generateSuggestions({
      value2_filter: this.state.value2Filter, value1_filter: this.state.value1Filter,
      comparator_filter: this.state.comparatorFilter,
      suggestions_template_value1: this.suggestionsTemplateRow && this.suggestionsTemplateRow.state.value1,
      suggestions_template_comparator: this.suggestionsTemplateRow && this.suggestionsTemplateRow.state.comparator,
      suggestions_template_value2: this.suggestionsTemplateRow && this.suggestionsTemplateRow.state.value2,
      checklist_mode: !!this.suggestionsTemplateRow
    }))
  }

  clearSuggestions(e) {
    e.preventDefault();
    e.stopPropagation();
    console.log("clearSuggestions");
    this.setState({suggestions_pos: 0, suggestions: []});
    this.comm.sendEvent(clearSuggestions());
  }

  pageSuggestions(e, direction) {
    e.preventDefault();
    e.stopPropagation();
    if (direction == "up") {
      this.setState({
        suggestions_pos: Math.max(0, this.state.suggestions_pos - this.state.max_suggestions)
      })
    } else {
      this.setState({
        suggestions_pos: this.state.suggestions_pos + this.state.max_suggestions
      })
    }
  }

  toggleSelection(id, shiftKey, metaKey) {
    console.log("toggleSelection", id, shiftKey, metaKey);
    
    if (!shiftKey && metaKey) {
      let selections = clone(this.state.selections);
      selections[id] = selections[id] ? false : true;
      this.setState({selections: selections});
    } else if (shiftKey) {
      const keys = Object.keys(this.state.selections);
      let first_selection_id = null;
      if (keys.length > 0) first_selection_id = keys[0];
      let selections = {};
      let selecting = false;
      console.log("first_selection_id", first_selection_id)
      for (let i = 0; i < this.state.suggestions.length; ++i) {
        const curr_id = this.state.suggestions[i];
        if (curr_id === id) {
          if (selecting) {
            selections[curr_id] = true;
            selecting = false;
          } else {
            selecting = true;
          }
        }
        if (curr_id === first_selection_id) {
          if (selecting) {
            selections[curr_id] = true;
            selecting = false;
          } else {
            selecting = true;
          }
        }
        if (selecting) {
          selections[curr_id] = true;
        }
      }
      for (let i = 0; i < this.state.tests.length; ++i) {
        const curr_id = this.state.tests[i];
        if (curr_id === id) {
          if (selecting) {
            selections[curr_id] = true;
            selecting = false;
          } else {
            selecting = true;
          }
        }
        if (curr_id === first_selection_id) {
          if (selecting) {
            selections[curr_id] = true;
            selecting = false;
          } else {
            selecting = true;
          }
        }
        if (selecting) {
          selections[curr_id] = true;
        }
      }
      
      this.setState({selections: selections});
    } else {
      const keys = Object.keys(this.state.selections);
      if (!this.state.selections[id]) {
        let selections = {};
        selections[id] = true;
        console.log("setting state from toggleSelection", keys, id)
        this.setState({selections: selections});
      }
    }
  }

  onSuggestionsDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  onSuggestionsDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    this.setState({suggestionsDropHighlighted: this.state.suggestionsDropHighlighted - 1});
  }

  onSuggestionsDragEnter(e) {
    console.log("eeenter", e.target)
    e.preventDefault();
    e.stopPropagation();
    this.setState({suggestionsDropHighlighted: this.state.suggestionsDropHighlighted + 1});
  }

  onSuggestionsDrop(e) {
    
    e.preventDefault();
    e.stopPropagation();
    const id = e.dataTransfer.getData("id");
    const topic_name = e.dataTransfer.getData("topic_name");
    console.log("onSuggestionsDrop", e, id);
    if (this.state.suggestions.indexOf(id) !== -1) return; // dropping a suggestion into suggestions should do nothing
    this.setState({suggestionsDropHighlighted: 0});
    if (topic_name !== null && topic_name !== "null") {
      this.onDrop(id, this.state.topic + "/__suggestions__" + "/" + topic_name);
    } else {
      this.onDrop(id, this.state.topic + "/__suggestions__");
    }
  }

  onDrop(id, topic) {
    console.log("onDrop", id, topic)
    let ids;
    if (this.state.selections[id]) {
      ids = Object.keys(this.state.selections);
      this.setState({selections: {}});
    } else ids = id;
    this.comm.sendEvent(moveTest(ids, topic));
  }

  goToTopic(topic) {
    console.log("goToTopic", topic);
    if (this.suggestionsTemplateRow) {
      this.suggestionsTemplateRow.setState({value2: null});
    }
    this.comm.sendEvent(changeTopic(stripSlash(topic).replaceAll(" ", "%20")))
  }

}

//const red_blue_100 = ["rgb(0.0,138.56128015770724,250.76166088685727,255.0)","rgb(0.0,137.4991163711455,250.4914687565557,255.0)","rgb(0.0,135.89085862817228,250.03922790292606,255.0)","rgb(0.0,134.80461722068503,249.69422979450337,255.0)","rgb(0.0,133.15912944070257,249.12764143629818,255.0)","rgb(0.0,132.04779673175938,248.70683279399356,255.0)","rgb(0.0,130.3634759186023,248.02444138814778,255.0)","rgb(0.0,128.65565323564863,247.27367576741693,255.0)","rgb(0.0,127.50110843874282,246.72753679433836,255.0)","rgb(0.0,125.75168029462561,245.85912208200173,255.0)","rgb(0.0,124.56903652403216,245.23521693285122,255.0)","rgb(0.0,122.77608206265468,244.24829742509777,255.0)","rgb(0.0,120.95599474876376,243.18984596934288,255.0)","rgb(0.0,119.72546791225868,242.44012441018438,255.0)","rgb(0.0,117.8591797836317,241.26416165478395,255.0)","rgb(0.0,116.59613419778282,240.4339311004283,255.0)","rgb(0.0,114.68050681628627,239.1383865197414,255.0)","rgb(0.0,113.3839993210777,238.2294590645131,255.0)","rgb(0.0,111.41634894068424,236.81437229328455,255.0)","rgb(24.588663906345325,109.41632410184977,235.32817682974928,255.0)","rgb(35.44735081278475,108.06183480151708,234.29254074792976,255.0)","rgb(48.051717444228224,106.00540836596966,232.68863110680456,255.0)","rgb(54.58382033054716,104.61144706132748,231.57374376885096,255.0)","rgb(63.262053865061056,102.49432802815242,229.85160463157354,255.0)","rgb(70.76957320138267,100.33771880021955,228.05703474246997,255.0)","rgb(75.30021073284686,98.87675486589102,226.81988465865538,255.0)","rgb(81.62949947778507,96.6540104818813,224.91180462302458,255.0)","rgb(85.51695933372014,95.1445958160281,223.59546445853985,255.0)","rgb(91.05223198159915,92.84880956154888,221.57285170783555,255.0)","rgb(94.50489166579793,91.28823726624896,220.18077895318467,255.0)","rgb(99.4583420952925,88.91232187683374,218.04471819705824,255.0)","rgb(104.12179041241362,86.48354864452708,215.84022539728738,255.0)","rgb(107.08110644040013,84.83182437240492,214.33114916353256,255.0)","rgb(111.35380618049061,82.31139742285828,212.01929775886506,255.0)","rgb(114.06578608562516,80.5910630456271,210.4357328916578,255.0)","rgb(118.00136409704606,77.96485213886614,208.016034988954,255.0)","rgb(121.74766173376136,75.26429120233696,205.5295010169315,255.0)","rgb(124.15338187699085,73.42230736362347,203.83759830570943,255.0)","rgb(127.6354972896637,70.59265795441205,201.2503012002821,255.0)","rgb(129.8659364639127,68.65218238542003,199.48871459726595,255.0)","rgb(133.10804101178616,65.66976521198737,196.80305057967465,255.0)","rgb(136.20117312715468,62.56838858187191,194.0535664536312,255.0)","rgb(138.1973647491704,60.43984691426682,192.1917348903892,255.0)","rgb(141.0812080782349,57.12602871008347,189.34981967460325,255.0)","rgb(142.93497217316724,54.83018307067161,187.42427995933073,255.0)","rgb(145.62183484149273,51.24379487478906,184.4934665197036,255.0)","rgb(147.34120668891256,48.72446502544426,182.50692554291248,255.0)","rgb(149.83882553726863,44.76410333626281,179.49010263854294,255.0)","rgb(152.21629692400205,40.46878966316789,176.41890349035555,255.0)","rgb(153.74537831964477,37.405899634336166,174.3463167526223,255.0)","rgb(156.8946867035305,33.63427487751921,172.10689873421705,255.0)","rgb(159.57052897508228,31.76356558772026,171.1904317530127,255.0)","rgb(163.51569605559672,28.753894553429824,169.77296032725718,255.0)","rgb(167.36700142841255,25.389234485648817,168.29649352383,255.0)","rgb(169.8939277417104,22.949167366394107,167.28653276271265,255.0)","rgb(173.60751889004476,18.751898233902914,165.72304707948427,255.0)","rgb(176.04037452587522,15.53349266017855,164.65367757038166,255.0)","rgb(179.62227517307235,9.586956240670718,163.00736797488793,255.0)","rgb(181.96398047712216,5.039485831605471,161.88104419124014,255.0)","rgb(185.4175817560734,0.0,160.1552802934102,255.0)","rgb(188.7866522134373,0.0,158.37821514882566,255.0)","rgb(190.99545744496794,0.0,157.1712500750526,255.0)","rgb(194.23939479374397,0.0,155.32022934668817,255.0)","rgb(196.3613372562259,0.0,154.06279982720955,255.0)","rgb(199.48227089890267,0.0,152.14184153517203,255.0)","rgb(202.52395205893734,0.0,150.17747004313574,255.0)","rgb(204.51720731357923,0.0,148.84941784048203,255.0)","rgb(207.43415034062437,0.0,146.8195255831636,255.0)","rgb(209.34227187082465,0.0,145.447819126977,255.0)","rgb(212.1382144344341,0.0,143.35790157156467,255.0)","rgb(214.85836244585704,0.0,141.23222265886395,255.0)","rgb(216.63670670950123,0.0,139.79905843731933,255.0)","rgb(219.23301240468484,0.0,137.6179798879229,255.0)","rgb(220.92924595032096,0.0,136.14914842114652,255.0)","rgb(223.4023955123896,0.0,133.91677798534914,255.0)","rgb(225.0139515716111,0.0,132.41381956928373,255.0)","rgb(227.36646430400836,0.0,130.13484833504174,255.0)","rgb(229.64256707387395,0.0,127.82818117110327,255.0)","rgb(231.1250651865189,0.0,126.27823065434256,255.0)","rgb(233.27714151990378,0.0,123.9294477401314,255.0)","rgb(234.676703289514,0.0,122.35230960074493,255.0)","rgb(236.70590614401792,0.0,119.96514396719735,255.0)","rgb(238.66106706741957,0.0,117.55637241505875,255.0)","rgb(239.92865207922344,0.0,115.94046512913654,255.0)","rgb(241.75947067582808,0.0,113.49767303291209,255.0)","rgb(242.94521123855867,0.0,111.86012465750336,255.0)","rgb(244.6516179552062,0.0,109.38587603007474,255.0)","rgb(245.75354715682175,0.0,107.72779565577645,255.0)","rgb(247.33745729848604,0.0,105.22467948947163,255.0)","rgb(248.84659658395643,0.0,102.70475812439781,255.0)","rgb(249.8170331745849,0.0,101.01697337568197,255.0)","rgb(251.20184136638093,0.0,98.47001746051721,255.0)","rgb(252.09049986637743,0.0,96.76466947151692,255.0)","rgb(253.35113135488535,0.0,94.19124565826175,255.0)","rgb(254.475785780405,0.0,91.60224197581371,255.0)","rgb(255.0,0.0,89.86831280400678,255.0)","rgb(255.0,0.0,87.25188871633031,255.0)","rgb(255.0,0.0,85.49944591423251,255.0)","rgb(255.0,0.0,82.8535189165512,255.0)","rgb(255.0,0.0,81.08083606031792,255.0)"]
const red_blue_100 = ["rgb(0.0, 199.0, 100.0)", "rgb(7.68, 199.88, 96.12)", "rgb(15.36, 200.76, 92.24)", "rgb(23.04, 201.64, 88.36)", "rgb(30.72, 202.52, 84.48)", "rgb(38.4, 203.4, 80.6)", "rgb(46.08, 204.28, 76.72)", "rgb(53.76, 205.16, 72.84)", "rgb(61.44, 206.04, 68.96)", "rgb(69.12, 206.92, 65.08)", "rgb(76.8, 207.8, 61.2)", "rgb(84.48, 208.68, 57.32)", "rgb(92.16, 209.56, 53.44)", "rgb(99.84, 210.44, 49.56)", "rgb(107.52, 211.32, 45.68)", "rgb(115.2, 212.2, 41.8)", "rgb(122.88, 213.08, 37.92)", "rgb(130.56, 213.96, 34.04)", "rgb(138.24, 214.84, 30.16)", "rgb(145.92, 215.72, 26.28)", "rgb(153.6, 216.6, 22.4)", "rgb(161.28, 217.48, 18.52)", "rgb(168.96, 218.36, 14.64)", "rgb(176.64, 219.24, 10.76)", "rgb(184.32, 220.12, 6.88)", "rgb(192.0, 221.0, 3.0)", "rgb(194.52, 220.12, 6.44)", "rgb(197.04, 219.24, 9.88)", "rgb(199.56, 218.36, 13.32)", "rgb(202.08, 217.48, 16.76)", "rgb(204.6, 216.6, 20.2)", "rgb(207.12, 215.72, 23.64)", "rgb(209.64, 214.84, 27.08)", "rgb(212.16, 213.96, 30.52)", "rgb(214.68, 213.08, 33.96)", "rgb(217.2, 212.2, 37.4)", "rgb(219.72, 211.32, 40.84)", "rgb(222.24, 210.44, 44.28)", "rgb(224.76, 209.56, 47.72)", "rgb(227.28, 208.68, 51.16)", "rgb(229.8, 207.8, 54.6)", "rgb(232.32, 206.92, 58.04)", "rgb(234.84, 206.04, 61.48)", "rgb(237.36, 205.16, 64.92)", "rgb(239.88, 204.28, 68.36)", "rgb(242.4, 203.4, 71.8)", "rgb(244.92, 202.52, 75.24)", "rgb(247.44, 201.64, 78.68)", "rgb(249.96, 200.76, 82.12)", "rgb(252.48, 199.88, 85.56)", "rgb(255.0, 199.0, 89.0)", "rgb(255.0, 197.36, 87.08)", "rgb(255.0, 195.72, 85.16)", "rgb(255.0, 194.08, 83.24)", "rgb(255.0, 192.44, 81.32)", "rgb(255.0, 190.8, 79.4)", "rgb(255.0, 189.16, 77.48)", "rgb(255.0, 187.52, 75.56)", "rgb(255.0, 185.88, 73.64)", "rgb(255.0, 184.24, 71.72)", "rgb(255.0, 182.6, 69.8)", "rgb(255.0, 180.96, 67.88)", "rgb(255.0, 179.32, 65.96)", "rgb(255.0, 177.68, 64.04)", "rgb(255.0, 176.04, 62.12)", "rgb(255.0, 174.4, 60.2)", "rgb(255.0, 172.76, 58.28)", "rgb(255.0, 171.12, 56.36)", "rgb(255.0, 169.48, 54.44)", "rgb(255.0, 167.84, 52.52)", "rgb(255.0, 166.2, 50.6)", "rgb(255.0, 164.56, 48.68)", "rgb(255.0, 162.92, 46.76)", "rgb(255.0, 161.28, 44.84)", "rgb(255.0, 159.64, 42.92)", "rgb(255.0, 158.0, 41.0)", "rgb(255.0, 153.25, 39.583)", "rgb(255.0, 148.5, 38.167)", "rgb(255.0, 143.75, 36.75)", "rgb(255.0, 139.0, 35.333)", "rgb(255.0, 134.25, 33.917)", "rgb(255.0, 129.5, 32.5)", "rgb(255.0, 124.75, 31.083)", "rgb(255.0, 120.0, 29.667)", "rgb(255.0, 115.25, 28.25)", "rgb(255.0, 110.5, 26.833)", "rgb(255.0, 105.75, 25.417)", "rgb(255.0, 101.0, 24.0)", "rgb(255.0, 96.25, 22.583)", "rgb(255.0, 91.5, 21.167)", "rgb(255.0, 86.75, 19.75)", "rgb(255.0, 82.0, 18.333)", "rgb(255.0, 77.25, 16.917)", "rgb(255.0, 72.5, 15.5)", "rgb(255.0, 67.75, 14.083)", "rgb(255.0, 63.0, 12.667)", "rgb(255.0, 58.25, 11.25)", "rgb(255.0, 53.5, 9.833)", "rgb(255.0, 48.75, 8.417)", "rgb(255.0, 44.0, 7.0)"]

function red_blue_color(value, min, max) {
  return red_blue_100[Math.floor(99.9999 * (value - min)/(max - min))]
}

function stripSlash(str) {
  return str.endsWith('/') ? str.slice(0, -1) : str;
}