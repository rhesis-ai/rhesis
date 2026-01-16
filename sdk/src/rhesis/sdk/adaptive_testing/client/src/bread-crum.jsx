import React from 'react';
import autoBind from 'auto-bind';

export default class BreadCrum extends React.Component {
  constructor(props) {
    super(props);
    autoBind(this);
    
    this.state = {
      dropHighlighted: 0
    };
  }

  render() {
    // console.log("br", this.props.name, this.props.name === "")
    return <div className={this.state.dropHighlighted ? "adatest-crum-selected" : ""} style={{borderRadius: "10px 10px 10px 10px", display: "inline-block", cursor: "pointer"}} 
          onClick={this.onClick} onDragOver={this.onDragOver} onDragEnter={this.onDragEnter}
          onDragLeave={this.onDragLeave} onDrop={this.onDrop}>
      {this.props.name === "" ? this.props.defaultName : decodeURIComponent(this.props.name)}
    </div>
  }

  onClick(e) {
    e.preventDefault();
    e.stopPropagation();
    if (this.props.onClick) {
      if (this.props.name === "") {
        this.props.onClick(this.props.topic);
      } else {
        this.props.onClick(this.props.topic + "/" + this.props.name);
      }
    }
  }

  onDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  onDragEnter(e) {
    e.preventDefault();
    e.stopPropagation();
    this.setState({dropHighlighted: this.state.dropHighlighted + 1});
  }

  onDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    this.setState({dropHighlighted: this.state.dropHighlighted - 1});
  }

  onDrop(e) {
    const id = e.dataTransfer.getData("id");
    this.setState({dropHighlighted: 0});
    if (this.props.onDrop) {
      let suffix = "";
      if (id.includes("/")) {
        suffix = "/" + id.split("/").pop();
      }
      this.props.onDrop(id, this.props.topic + (this.props.name === "" ? "" : "/" + this.props.name) + suffix);
    }
  }
}