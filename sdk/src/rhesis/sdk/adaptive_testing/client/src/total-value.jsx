import React from 'react';
import autoBind from 'auto-bind';
import { get, debounce } from 'lodash';

export default class TotalValue extends React.Component {
    constructor(props) {
      super(props);
      autoBind(this);

      this.doStateUpdateDebounced = debounce(this.doStateUpdate, 100);

      this.pendingStateUpdate = {};
  
      // our starting state 
      this.state = {
        // note that all the ids will also be properties of the state
      };
    }
  
    setSubtotal(id, subtotal) {
      this.pendingStateUpdate[id] = subtotal;
      this.doStateUpdateDebounced();
    }

    doStateUpdate() {
      this.setState(this.pendingStateUpdate);
      this.pendingStateUpdate = {};
    }
  
    render() {
      // we just sum up the current active subtotals
      let total = 0;
      for (let i in this.props.activeIds) {
        total += get(this.state, this.props.activeIds[i], 0);
      }
      
      return <span>
        {total}
      </span>
    }
  }