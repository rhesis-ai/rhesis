import "./adatest.css";

import React from 'react';
import ReactDOM from 'react-dom';
import { withRouter } from 'react-router-dom';
import { BrowserRouter } from "react-router-dom";
import { MemoryRouter } from 'react-router';
import Browser from './browser'

const BrowserWithRouter = withRouter(Browser);

export default class AdaTest extends React.Component {

  constructor(props) {
    super(props);
    console.log("interfaceId", this.props.interfaceId)
    this.state = { enabled: true };
    window.adatest_root = this;
  }
  render() {

    const Router = this.props.environment === "web" ? BrowserRouter : MemoryRouter;

    return (
      <div style={{maxWidth: "1000px", marginLeft: "auto", marginRight: "auto"}}>
        <div style={{paddingLeft: "0px", width: "100%", fontFamily: "Helvetica Neue, Helvetica, Arial, sans-serif", boxSizing: "border-box", fontSize: "13px", opacity: this.state.enabled ? 1 : 0.4}}>
          <Router>
            <BrowserWithRouter
              interfaceId={this.props.interfaceId} environment={this.props.environment}
              websocket_server={this.props.websocket_server} enabled={this.state.enabled}
              startingTopic={this.props.startingTopic} prefix={this.props.prefix}
            />
          </Router>
        </div>
      </div>
    );
  }
}

window.AdaTestReact = React
window.AdaTestReactDOM = ReactDOM
window.AdaTest = AdaTest

