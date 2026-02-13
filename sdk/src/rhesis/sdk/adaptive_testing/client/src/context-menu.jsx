import React from 'react';
import autoBind from 'auto-bind';

export default class ContextMenu extends React.Component {
  static defaultProps = {
    top: 0,
    left: 0,
    open: false,
    onClick: () => undefined,
    rows: [
      "test"
    ]
  };

  constructor(props) {
    super(props);
    autoBind(this);
  }

  render() {
    return <div style={{display: this.props.open ? "inline-block" : "none"}}>
      <div style={{position: "fixed", top: 0, bottom: 0, left: 0, right: 0}} onClick={this.handleBackgroundClick}></div>
      <div style={{position: "absolute", top: this.props.top, left: this.props.left, background: "#ffffff", padding: "4px", boxShadow: "0px 2px 5px #666666"}}>
        {this.props.rows && this.props.rows.map((row, index) => {
          return <div key={index} onClick={e => this.handleRowClick(row, e)} className="adatest-hover-gray">{row}</div>
        })}
      </div>
    </div>
  }

  handleBackgroundClick(e) {
    e.preventDefault();
    this.props.onClose();
  }

  handleRowClick(row, e) {
    e.preventDefault();
    this.props.onClick(row);
  }
}